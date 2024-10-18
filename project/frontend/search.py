import streamlit as st
import pandas as pd
import requests
import base64
from config import API_URL

def flatten_nested_fields(candidate):
    """Helper function to flatten nested fields for display."""
    # Flattening education
    if candidate.get("education"):
        candidate["education"] = "; ".join([f"{edu['degree']} from {edu['institution_name']} (GPA: {edu.get('gpa', 'N/A')})" for edu in candidate["education"]])
    
    # Flattening experience
    if candidate.get("experience"):
        candidate["experience"] = "; ".join([f"{exp['job_title']} at {exp['company_name']}" for exp in candidate["experience"]])
    
    # Flattening certificates
    if candidate.get("certificates"):
        candidate["certificates"] = "; ".join([f"{cert['certificate_name']} (Level: {cert.get('certificate_point_level', 'N/A')})" for cert in candidate["certificates"]])
    else:
        candidate["certificates"] = ""  # Ensure this is an empty string if no certificates

    # Flattening projects
    if candidate.get("projects"):
        candidate["projects"] = "; ".join([f"{proj['project_name']}: {', '.join(proj['detailed_descriptions'])}" for proj in candidate["projects"]])
    else:
        candidate["projects"] = ""  # Ensure this is an empty string if no projects

    # Flattening awards
    if candidate.get("awards"):
        candidate["awards"] = "; ".join([f"{award['award_name']} ({award.get('description', 'N/A')})" for award in candidate["awards"]])
    else:
        candidate["awards"] = ""  # Ensure this is an empty string if no awards

    return candidate

def search_candidates():
    st.title("Candidate Search with PDF Preview")

    # Fetch folders for the current user
    response = requests.get(f"{API_URL}/folders", headers={"Authorization": f"Bearer {st.session_state.token}"})
    if response.status_code == 200:
        folders = response.json()
        if not folders:
            st.warning("You don't have any folders yet. Please create one to start searching.")
            return

        # Allow user to select folders
        folder_options = [folder['name'] for folder in folders]
        selected_folders = st.multiselect("Select Folders", folder_options)

        if st.button("Confirm Folders"):
            if selected_folders:
                st.session_state.selected_folders = selected_folders  # Store selected folders in session state
                st.success("Folders confirmed. You can now fill in the search fields.")

        if "selected_folders" in st.session_state:
            with st.form("search_form"):
                col1, col2, col3 = st.columns([1, 1, 1])

                # Dynamically fetch options for filters from the API based on the selected folders
                def fetch_filter_options(field):
                    response = requests.get(
                        f"{API_URL}/search/fetch_cv_info",
                        params={"folder_names": st.session_state.selected_folders, "field": field},
                        headers={"Authorization": f"Bearer {st.session_state.token}"}
                    )
                    if response.status_code == 200:
                        return response.json().get(field, [])
                    else:
                        st.error(f"Failed to fetch {field} options.")
                        return []

                with col1:
                    job_title = st.multiselect("Job Title", options=fetch_filter_options("job_titles"))
                    industry = st.multiselect("Industry", options=fetch_filter_options("industries"))
                    country = st.multiselect("Country", options=fetch_filter_options("countries"))
                    degree = st.multiselect("Degree", options=fetch_filter_options("degrees"))
                    yoe = st.number_input("Years of Experience (Min)", min_value=0, max_value=30, value=0)

                with col2:
                    current_job = st.text_input("Current Job")
                    city = st.multiselect("City", options=fetch_filter_options("cities"))
                    language = st.text_input("Language")
                    major = st.multiselect("Major", options=fetch_filter_options("majors"))
                    point = st.number_input("Points (Min)", min_value=0.0, max_value=10.0, value=0.0, step=0.5, format="%.2f")

                with col3:
                    skills = st.multiselect("Skills", options=fetch_filter_options("skills"))
                    level = st.text_input("Level")
                    age = st.number_input("Age (Min)", min_value=0, max_value=70, value=0)

                search_button = st.form_submit_button("Search")

            if search_button:
                search_params = {
                    "job_title": job_title if job_title else None,
                    "current_job": [current_job] if current_job else None,
                    "industry": industry if industry else None,
                    "city": city if city else None,
                    "country": country if country else None,
                    "language": [language] if language else None,
                    "skill": skills if skills else None,
                    "degree": degree if degree else None,
                    "major": major if major else None,
                    "level": [level] if level else None,
                    "yoe_range": [yoe, 30] if yoe > 0 else None,
                    "point_range": [point, 100] if point > 0 else None,
                    "folder_names": st.session_state.selected_folders,
                    "old_range": [age, 70] if age > 0 else None,
                }
                search_params = {k: v for k, v in search_params.items() if v}

                response = requests.post(
                    f"{API_URL}/search/candidates",
                    json=search_params,
                    headers={"Authorization": f"Bearer {st.session_state.token}"}
                )

                if response.status_code == 200:
                    candidates = response.json()
                    if candidates:
                        # Store the search results in session state to persist them across reruns
                        st.session_state.candidates = [flatten_nested_fields(candidate) for candidate in candidates]

    # Display search results if they exist
    if 'candidates' in st.session_state:
        candidates = st.session_state.candidates
        df = pd.DataFrame(candidates)

        # Add a checkbox column to allow selecting rows in the main DataFrame
        df['Select'] = False  # Add a select column with default False
        columns = ['Select'] + [col for col in df.columns if col != 'Select']
        df = df[columns]

        # Show table with checkboxes for the main DataFrame
        edited_df = st.data_editor(
            df,
            hide_index=True,
            column_config={
                "Select": st.column_config.CheckboxColumn(required=True),
            },
            disabled=df.columns.drop(['Select']),
            key="candidate_table"
        )

        # Store selected candidates in session state
        selected_candidates = edited_df[edited_df['Select']]
        st.session_state.selected_candidates = selected_candidates

        if not selected_candidates.empty:
            col1, col2 = st.columns([1, 1])
            with col1:
                # Preview Selected Candidate
                if st.button("Preview Selected Candidate"):
                    if len(selected_candidates) == 1:
                        selected_candidate_idx = selected_candidates.index[0]
                        file_id = candidates[selected_candidate_idx]["file_id"]  # Assuming each candidate has a file_id

                        # Display PDF preview
                        if file_id:
                            pdf_display = view_file(file_id, selected_candidates.iloc[0]["job_title"])
                            if pdf_display:
                                st.markdown(pdf_display, unsafe_allow_html=True)
                            else:
                                st.error("Failed to load the file preview.")
                    elif len(selected_candidates) > 1:
                        st.warning("Please select only one candidate for preview.")
                    else:
                        st.warning("No candidate selected for preview.")
        else:
            st.info("No candidate selected.")
    else:
        st.warning("No search results available. Please perform a search.")

def view_file(file_id, filename):
    """View the PDF file by embedding it in the app."""
    response = requests.get(f"{API_URL}/files/{file_id}/download", headers={"Authorization": f"Bearer {st.session_state.token}"})

    if response.status_code == 200:
        pdf_data = response.content
        base64_pdf = base64.b64encode(pdf_data).decode('utf-8')
        pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="700" height="1000" type="application/pdf"></iframe>'
        return pdf_display
    else:
        return None
