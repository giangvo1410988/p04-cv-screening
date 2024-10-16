from config import API_URL
import requests
import streamlit as st
import pandas as pd
from streamlit_tags import st_tags
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

        # If folders are selected, show search filters
        if selected_folders:
            # Divide search filters into columns for a cleaner layout
            with st.form("search_form"):
                col1, col2, col3 = st.columns([1, 1, 1])
                
                with col1:
                    job_title = st.text_input("Job Title")
                    industry = st.text_input("Industry")
                    country = st.text_input("Country")
                    degree = st.text_input("Degree")
                    yoe = st.number_input("Years of Experience (Min)", min_value=0, max_value=30, value=0)

                with col2:
                    current_job = st.text_input("Current Job")
                    city = st.text_input("City")
                    language = st.text_input("Language")
                    major = st.text_input("Major")
                    point = st.number_input("Points (Min)", min_value=0, max_value=100, value=0)

                with col3:
                    # Use st_tags for dynamic input of multiple skills
                    skills = st_tags(
                        label="Skills",
                        text="Add skills (press enter to add more)",
                        value=[],
                        suggestions=[],  # If you want to suggest some skills
                        maxtags=20,
                    )
                    level = st.text_input("Level")
                    age = st.number_input("Age (Min)", min_value=0, max_value=70, value=0)

                # Submit button
                search_button = st.form_submit_button("Search")

                if search_button:
                    # Convert input values to None if they are 0 or empty
                    search_params = {
                        "job_title": [job_title] if job_title else None,
                        "current_job": [current_job] if current_job else None,
                        "industry": [industry] if industry else None,
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
