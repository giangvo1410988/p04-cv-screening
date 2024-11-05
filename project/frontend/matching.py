import streamlit as st
import requests
import pandas as pd
import base64

# API URL for your FastAPI endpoints
from config import API_URL
def display_candidate_results(candidates):
    """Helper function to display candidate results with scoring information"""
    # Create DataFrame
    df = pd.DataFrame(candidates)
    
    # Calculate percentage matches and add columns
    if df.empty:
        return None

    # Add Select column at the start
    df.insert(0, 'Select', False)

    # Configure columns for better display
    column_config = {
        "Select": st.column_config.CheckboxColumn(required=True),
        "full_name": st.column_config.TextColumn("Full Name"),
        "job_title": st.column_config.TextColumn("Job Title"),
        "weighted_similarity": st.column_config.ProgressColumn(
            "Match Score",
            help="Overall match score",
            format="%.0f%%",
            min_value=0,
            max_value=100
        ),
        "skills": st.column_config.ListColumn("Skills"),
        "experience": st.column_config.TextColumn("Experience"),
        "education": st.column_config.TextColumn("Education"),
        "yoe": st.column_config.NumberColumn("Years of Experience"),
    }

    # Show the DataFrame
    return st.data_editor(
        df,
        hide_index=True,
        column_config=column_config,
        disabled=df.columns.drop(['Select']),
        key=f"candidate_table_{hash(str(df.values.tolist()))}"
    )

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
        "job_title": job_description_data_copy.get("job_title", ""),
        "industry": job_description_data_copy.get("industry", ""),
        "company_name": job_description_data_copy.get("company_name", ""),
        "level": job_description_data_copy.get("level", ""),
        "salary": job_description_data_copy.get("salary", ""),
        "start_time": job_description_data_copy.get("start_time", "")
    }

    # Extract location fields
    location_table = pd.DataFrame([job_description_data_copy.get("location", {})])

    # Extract job requirements
    job_requirements = job_description_data_copy.get("job_requirements", {})

    # Create skills, experience, education, and points tables
    skills_table = pd.DataFrame(job_requirements.get("skills", []), columns=["skills"])
    experience_table = pd.DataFrame([job_requirements.get("experience", {})])
    education_table = pd.DataFrame([job_requirements.get("education", {})])
    points_table = pd.DataFrame([job_requirements.get("points", {})])

    # Convert the main table into a DataFrame
    main_table_df = pd.DataFrame([main_table])

    # Return all the tables
    return main_table_df, location_table, skills_table, experience_table, education_table, points_table



def job_description_search():
    st.title("AI Resume Matching")

    # Clear session state when starting new search
    if st.button("Clear Previous Results"):
        if 'candidates' in st.session_state:
            del st.session_state.candidates
        if 'candidate_table_data' in st.session_state:
            del st.session_state.candidate_table_data
        st.success("Previous results cleared.")
        st.rerun()

    # Fetch folders for the current user first
    response = requests.get(f"{API_URL}/folders", headers={"Authorization": f"Bearer {st.session_state.token}"})
    if response.status_code == 200:
        folders = response.json()
        if not folders:
            st.warning("You don't have any folders yet. Please create one to start searching.")
            return

        # Allow user to select folders
        folder_options = [folder['name'] for folder in folders]
        selected_folders = st.multiselect("Select Folders to Search In", folder_options)

        if st.button("Confirm Folders"):
            if selected_folders:
                if 'candidates' in st.session_state:
                    del st.session_state.candidates
                if 'candidate_table_data' in st.session_state:
                    del st.session_state.candidate_table_data
                st.session_state.selected_folders = selected_folders
                st.success("Folders confirmed. You can now proceed with uploading the job description.")
                st.rerun()
            else:
                st.warning("Please select at least one folder.")
                return

        # Only show the rest of the interface if folders are selected
        if "selected_folders" in st.session_state:
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
                            st.session_state.job_description_data = job_description_data
                            st.success("Job description extracted successfully.")
                        else:
                            st.error(f"Failed to extract job description. Status code: {response.status_code}")
                            st.error(f"Error message: {response.text}")

            # Display the parsed job description data if it exists
            if "job_description_data" in st.session_state:
                st.subheader("Parsed Job Description Data")

                job_description_data_copy = st.session_state.job_description_data.copy()
                job_description_data_copy['folder_names'] = st.session_state.selected_folders

                # Display the parsed tables
                main_table_df, location_table, skills_table, experience_table, education_table, points_table = create_nested_tables(job_description_data_copy)

                st.subheader("Main Info")
                st.dataframe(main_table_df)
                
                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("Location")
                    st.dataframe(location_table)
                    
                    st.subheader("Skills")
                    st.dataframe(skills_table)
                
                with col2:
                    st.subheader("Experience")
                    st.dataframe(experience_table)
                    
                    st.subheader("Education")
                    st.dataframe(education_table)
                    
                    st.subheader("Points")
                    st.dataframe(points_table)

                # AI Search section
                st.subheader("AI Search")

                # Button to search candidates based on job description
                if st.button("Find CV With AI"):
                    if 'candidates' in st.session_state:
                        del st.session_state.candidates
                    if 'candidate_table_data' in st.session_state:
                        del st.session_state.candidate_table_data

                    with st.spinner("Searching for candidates using embedding and full-text search..."):
                        search_payload = {
                            **st.session_state.job_description_data,
                            "folder_names": st.session_state.selected_folders
                        }

                        search_response = requests.post(
                            f"{API_URL}/matching/hybrid_search",
                            json=search_payload,
                            headers={"Authorization": f"Bearer {st.session_state.token}"}
                        )

                        if search_response.status_code == 200:
                            response_data = search_response.json()
                            results = response_data.get('results', [])
                            stats = response_data.get('stats', {})
                            
                            if results:
                                st.success(f"Found {len(results)} candidates in the selected folders.")
                                
                                # Display summary metrics
                                st.subheader("Match Summary")
                                col1, col2, col3 = st.columns(3)
                                with col1:
                                    st.metric("Average Match Score", f"{stats.get('avg_similarity', 0):.0%}")
                                with col2:
                                    st.metric("Best Match", f"{stats.get('max_similarity', 0):.0%}")
                                with col3:
                                    st.metric("Skills Coverage", f"{stats.get('skills_coverage', 0):.1f}")

                                # Process candidates
                                processed_candidates = []
                                for candidate in results:
                                    processed = flatten_nested_fields(candidate)
                                    # Add score as percentage
                                    processed['match_score'] = candidate.get('weighted_similarity', 0) * 100
                                    processed_candidates.append(processed)
                                
                                # Create DataFrame with scores
                                df = pd.DataFrame(processed_candidates)
                                df['Select'] = False
                                
                                # Reorder columns
                                score_columns = ['Select', 'full_name', 'job_title', 'match_score', 
                                               'industry', 'yoe', 'skills', 'education', 'experience']
                                available_columns = [col for col in score_columns if col in df.columns]
                                other_columns = [col for col in df.columns if col not in score_columns]
                                df = df[available_columns + other_columns]
                                
                                # Configure column display
                                column_config = {
                                    "Select": st.column_config.CheckboxColumn(required=True),
                                    "match_score": st.column_config.ProgressColumn(
                                        "Match Score",
                                        help="Overall match score",
                                        format="%d%%",
                                        min_value=0,
                                        max_value=100,
                                    ),
                                    "skills": st.column_config.ListColumn("Skills"),
                                }

                                # Store in session state
                                st.session_state.candidates = processed_candidates
                                st.session_state.candidate_table_data = df
                                
                                # Display candidates table
                                edited_df = st.data_editor(
                                    df,
                                    hide_index=True,
                                    column_config=column_config,
                                    disabled=df.columns.drop(['Select']),
                                    key=f"candidate_table_{hash(str(df.values.tolist()))}"
                                )
                                
                                st.session_state.candidate_table_data = edited_df
                                
                                # Handle selected candidates
                                selected_candidates = edited_df[edited_df['Select']]
                                st.session_state.selected_candidates = selected_candidates

                                if not selected_candidates.empty:
                                    if st.button("Preview Selected Candidate"):
                                        if len(selected_candidates) == 1:
                                            selected_candidate = selected_candidates.iloc[0]
                                            file_id = selected_candidate.get("file_id")

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
                            else:
                                st.warning("No candidates found in the selected folders.")
                        else:
                            st.error(f"Failed to search candidates. Status code: {search_response.status_code}")
                            st.error(f"Error message: {search_response.text}")
    else:
        st.error(f"Failed to fetch folders. Status code: {response.status_code}")


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