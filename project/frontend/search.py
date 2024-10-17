from config import API_URL
import requests
import streamlit as st
import pandas as pd
from pathlib import Path

def search_candidates():
    st.title("Candidate Search")

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

        # Add a button to confirm folder selection
        if st.button("Confirm Folders"):
            if selected_folders:
                # Fetch CV information for the selected folders
                with st.spinner("Fetching CV information..."):
                    response = requests.get(
                        f"{API_URL}/search/fetch_cv_info",
                        params={"folder_names": selected_folders},
                        headers={"Authorization": f"Bearer {st.session_state.token}"}
                    )
                    if response.status_code == 200:
                        cv_info = response.json()
                        st.session_state.cv_info = cv_info  # Store fetched CV info in session state
                        st.success("CV information fetched successfully. You can now fill in the search fields.")
                    else:
                        st.error("Failed to fetch CV information.")
                        st.error(f"Error message: {response.text}")

        # If folders are confirmed and CV information is available, display search filters
        if selected_folders and "cv_info" in st.session_state:
            # Divide search filters into columns for a cleaner layout
            with st.form("search_form"):
                col1, col2, col3 = st.columns([1, 1, 1])

                # Populate form fields with fetched CV information as suggestions
                with col1:
                    job_title = st.multiselect("Job Title", options=st.session_state.cv_info["job_titles"])
                    industry = st.multiselect("Industry", options=st.session_state.cv_info["industries"])
                    country = st.multiselect("Country", options=st.session_state.cv_info["countries"])
                    degree = st.multiselect("Degree", options=st.session_state.cv_info["degrees"])
                    yoe = st.number_input("Years of Experience (Min)", min_value=0, max_value=30, value=0)

                with col2:
                    current_job = st.text_input("Current Job")
                    city = st.multiselect("City", options=st.session_state.cv_info["cities"])
                    language = st.text_input("Language")
                    major = st.multiselect("Major", options=st.session_state.cv_info["majors"])
                    point = st.number_input("Points (Min)", min_value=0, max_value=100, value=0)

                with col3:
                    # Use st.multiselect for skills with predefined suggestions
                    skills = st.multiselect(
                        "Skills",
                        options=st.session_state.cv_info["skills"],
                    )
                    level = st.text_input("Level")
                    age = st.number_input("Age (Min)", min_value=0, max_value=70, value=0)

                # Submit button
                search_button = st.form_submit_button("Search")

                if search_button:
                    # Convert input values to None if they are 0 or empty
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
                        "folder_names": selected_folders,
                        "old_range": [age, 70] if age > 0 else None,
                    }
                    search_params = {k: v for k, v in search_params.items() if v}  # Remove empty parameters

                    # Perform the search
                    response = requests.post(
                        f"{API_URL}/search/candidates",
                        json=search_params,
                        headers={"Authorization": f"Bearer {st.session_state.token}"}
                    )

                    if response.status_code == 200:
                        candidates = response.json()
                        if candidates:
                            # Display results
                            st.success(f"Found {len(candidates)} candidates.")
                            df = pd.DataFrame(candidates)
                            st.dataframe(df)
                        else:
                            st.warning("No candidates found.")
                    else:
                        st.error(f"Failed to search candidates. Status code: {response.status_code}")
                        st.error(f"Error message: {response.text}")

    else:
        st.error("Failed to fetch folders.")
        st.error(f"Error message: {response.text}")
