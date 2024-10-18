import streamlit as st
import requests
import pandas as pd
import base64

# API URL for your FastAPI endpoints
from config import API_URL

def view_file(file_id):
    """View the PDF file by embedding it in the app."""
    # Request to download the PDF file from the API
    response = requests.get(
        f"{API_URL}/files/{file_id}/download",
        headers={"Authorization": f"Bearer {st.session_state.token}"}
    )

    if response.status_code == 200:
        # Convert the PDF data to base64
        pdf_data = response.content
        base64_pdf = base64.b64encode(pdf_data).decode('utf-8')
        # Create the iframe to embed the PDF in the Streamlit app
        pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="700" height="1000" type="application/pdf"></iframe>'
        return pdf_display
    else:
        return None

def create_nested_tables(job_description_data_copy):
    """Helper function to separate out and return flattened nested fields for display, using a copy of job_description_data."""
    
    # Create main table (copy the relevant fields so the original data is unchanged)
    main_table = {
        "job_title": job_description_data_copy["job_title"],
        "industry": job_description_data_copy["industry"],
        "company_name": job_description_data_copy["company_name"],
        "employment_type": job_description_data_copy["employment_type"],
        "level": job_description_data_copy["level"],
        "salary": job_description_data_copy["salary"],
        "start_time": job_description_data_copy["start_time"]
    }

    # Separate tables for nested fields
    location_table = pd.DataFrame([job_description_data_copy["location"]])  # Extract location
    age_range_table = pd.DataFrame([job_description_data_copy["age_range"]])  # Extract age range
    
    # Extract job requirements
    job_requirements = job_description_data_copy["job_requirements"]
    skills_table = pd.DataFrame(job_requirements["skills"], columns=["skills"])
    experience_table = pd.DataFrame([job_requirements["experience"]])
    education_table = pd.DataFrame([job_requirements["education"]])
    points_table = pd.DataFrame([job_requirements["points"]])
    
    # Convert the main table into a DataFrame
    main_table_df = pd.DataFrame([main_table])
    
    # Return all the tables
    return main_table_df, location_table, age_range_table, skills_table, experience_table, education_table, points_table


def job_description_search():
    st.title("AI Resume Matching")

    # Upload job description PDF
    uploaded_file = st.file_uploader("Upload Job Description PDF", type=["pdf"])

    if uploaded_file:
        # Extract job description information
        if st.button("Extract Information from PDF"):
            with st.spinner("Extracting information from job description..."):
                files = {"file": uploaded_file.getvalue()}
                response = requests.post(
                    f"{API_URL}/matching/parse",
                    files=files,
                    headers={"Authorization": f"Bearer {st.session_state.token}"}
                )

                if response.status_code == 200:
                    job_description_data = response.json()
                    st.session_state.job_description_data = job_description_data  # Store data in session state
                    st.success("Job description extracted successfully.")
                else:
                    st.error(f"Failed to extract job description. Status code: {response.status_code}")
                    st.error(f"Error message: {response.text}")

    # Display the parsed job description data if it exists
    if "job_description_data" in st.session_state:
        st.subheader("Parsed Job Description Data")

        # Make a copy of job_description_data to avoid modifying the original data
        job_description_data_copy = st.session_state.job_description_data.copy()

        # Separate nested fields into tables using the copied data
        (
            main_table_df, 
            location_table, 
            age_range_table, 
            skills_table, 
            experience_table, 
            education_table, 
            points_table
        ) = create_nested_tables(job_description_data_copy)

        # Display main table
        st.subheader("Main Info")
        st.dataframe(main_table_df)

        # Display location table
        st.subheader("Location")
        st.dataframe(location_table)

        # Display age range table
        st.subheader("Age Range")
        st.dataframe(age_range_table)

        # Display skills table
        st.subheader("Skills")
        st.dataframe(skills_table)

        # Display experience table
        st.subheader("Experience")
        st.dataframe(experience_table)

        # Display education table
        st.subheader("Education")
        st.dataframe(education_table)

        # Display points table
        st.subheader("Points")
        st.dataframe(points_table)

        # Embedding-based search option
        st.subheader("AI Search")

        # Button to search candidates based on job description
        if st.button("Find CV With AI"):
            with st.spinner("Searching for candidates using embedding and full-text search..."):
                job_description_text = st.session_state.job_description_data['job_title']

                # Prepare the payload
                search_payload = {
                    "query": job_description_text
                }
                # Send the request
                search_response = requests.post(
                    f"{API_URL}/matching/hybrid_search",
                    json=search_payload,  # Send as JSON payload
                    headers={"Authorization": f"Bearer {st.session_state.token}"}
                )

            if search_response.status_code == 200:
                response_data = search_response.json()
                candidates = response_data.get('results', [])
                if candidates:
                    # Flatten nested fields
                    candidates = [flatten_nested_fields(candidate) for candidate in candidates]
                    # Store candidates in session state
                    st.session_state.candidates = candidates
                    st.success(f"Found {len(candidates)} candidates.")
                else:
                    st.warning("No candidates found.")
            else:
                st.error(f"Failed to search candidates. Status code: {search_response.status_code}")
                st.error(f"Error message: {search_response.text}")

    # Display candidates if they exist in session state
    if 'candidates' in st.session_state:
        # Check if 'candidate_table_data' exists to preserve selections
        if 'candidate_table_data' in st.session_state:
            df = st.session_state.candidate_table_data
        else:
            df = pd.DataFrame(st.session_state.candidates)
            # Ensure 'file_id' is included
            if 'file_id' not in df.columns:
                st.error("The 'file_id' column is missing from the data.")
                return
            df['Select'] = False  # Initialize 'Select' column

        columns = ['Select'] + [col for col in df.columns if col != 'Select']
        df = df[columns]

        # Display DataFrame with checkboxes
        edited_df = st.data_editor(
            df,
            hide_index=True,
            column_config={
                "Select": st.column_config.CheckboxColumn(required=True),
            },
            disabled=df.columns.drop(['Select']),
            key="candidate_table"
        )

        # Store the updated DataFrame including selections
        st.session_state.candidate_table_data = edited_df

        # Get selected candidates
        selected_candidates = edited_df[edited_df['Select']]
        st.session_state.selected_candidates = selected_candidates

        if not selected_candidates.empty:
            col1, col2 = st.columns([1, 1])
            with col1:
                # Preview Selected Candidate
                if st.button("Preview Selected Candidate"):
                    if len(selected_candidates) == 1:
                        selected_candidate = selected_candidates.iloc[0]
                        file_id = selected_candidate.get("file_id")

                        # Display PDF preview
                        if file_id:
                            pdf_display = view_file(file_id)
                            if pdf_display:
                                st.markdown(pdf_display, unsafe_allow_html=True)
                            else:
                                st.error("Failed to load the file preview.")
                        else:
                            st.error("File ID is missing.")
                    elif len(selected_candidates) > 1:
                        st.warning("Please select only one candidate for preview.")
                    else:
                        st.warning("No candidate selected for preview.")
        else:
            st.info("No candidate selected.")


def flatten_nested_fields(candidate):
    """Helper function to flatten nested fields for display."""
    # Flattening education
    if candidate.get("education"):
        candidate["education"] = "; ".join([
            f"{edu.get('degree', 'N/A')} from {edu.get('institution_name', 'N/A')} (GPA: {edu.get('gpa', 'N/A')})"
            for edu in candidate["education"]
        ])
    else:
        candidate["education"] = ""  # Ensure this is an empty string if no education

    # Flattening experience
    if candidate.get("experience"):
        candidate["experience"] = "; ".join([
            f"{exp.get('job_title', 'N/A')} at {exp.get('company_name', 'N/A')}"
            for exp in candidate["experience"]
        ])
    else:
        candidate["experience"] = ""  # Ensure this is an empty string if no experience

    # Flattening certificates
    if candidate.get("certificates"):
        candidate["certificates"] = "; ".join([
            f"{cert.get('certificate_name', 'N/A')} (Level: {cert.get('certificate_point_level', 'N/A')})"
            for cert in candidate["certificates"]
        ])
    else:
        candidate["certificates"] = ""  # Ensure this is an empty string if no certificates

    # Flattening projects
    if candidate.get("projects"):
        candidate["projects"] = "; ".join([
            f"{proj.get('project_name', 'N/A')}: {', '.join(proj.get('detailed_descriptions', []))}"
            for proj in candidate["projects"]
        ])
    else:
        candidate["projects"] = ""  # Ensure this is an empty string if no projects

    # Flattening awards
    if candidate.get("awards"):
        candidate["awards"] = "; ".join([
            f"{award.get('award_name', 'N/A')} ({award.get('description', 'N/A')})"
            for award in candidate["awards"]
        ])
    else:
        candidate["awards"] = ""  # Ensure this is an empty string if no awards

    return candidate