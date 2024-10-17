import streamlit as st
import requests
import json
from io import BytesIO
from config import API_URL
import pandas as pd

def job_description_search():
    st.title("Job Description Search")

    # Upload job description PDF
    uploaded_file = st.file_uploader("Upload Job Description PDF", type=["pdf"])

    if uploaded_file:
        # Extract job description information
        if st.button("Extract Information from PDF"):
            with st.spinner("Extracting information from job description..."):
                files = {"file": uploaded_file.getvalue()}
                response = requests.post(
                    f"{API_URL}/search/parse",
                    files=files,
                    headers={"Authorization": f"Bearer {st.session_state.token}"}
                )

                if response.status_code == 200:
                    job_description_data = response.json()
                    st.session_state.job_description_data = job_description_data  # Store data in session state
                    st.success("Job description extracted successfully.")
                    st.json(job_description_data)

    # Display search candidates button only if job description data is in session state
    if "job_description_data" in st.session_state:
        if st.button("Search Candidates"):
            with st.spinner("Searching for candidates..."):
                search_response = requests.post(
                    f"{API_URL}/search/search_from_job_description",
                    json=st.session_state.job_description_data,  # Use stored job description data
                    headers={"Authorization": f"Bearer {st.session_state.token}"}
                )

                if search_response.status_code == 200:
                    candidates = search_response.json()
                    if candidates:
                        # Display results
                        st.success(f"Found {len(candidates)} candidates.")
                        df = pd.DataFrame(candidates)
                        st.dataframe(df)
                    else:
                        st.warning("No candidates found.")
                else:
                    st.error(f"Failed to search candidates. Status code: {search_response.status_code}")
                    st.error(f"Error message: {search_response.text}")
