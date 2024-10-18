import streamlit as st
import requests
import json
import pandas as pd
import openai


# API URL for your FastAPI endpoints
from config import API_URL


def job_description_search():
    st.title("Job Description Search with Embedding-Based and Full-Text Search")

    # Upload job description PDF
    uploaded_file = st.file_uploader("Upload Job Description PDF", type=["pdf"])

    if uploaded_file:
        # Extract job description information
        if st.button("Extract Information from PDF"):
            with st.spinner("Extracting information from job description..."):
                files = {"file": uploaded_file.getvalue()}
                response = requests.post(
                    f"{API_URL}/matching/parse",  # Updated URL to match embedding-based flow
                    files=files,
                    headers={"Authorization": f"Bearer {st.session_state.token}"}
                )

                if response.status_code == 200:
                    job_description_data = response.json()
                    st.session_state.job_description_data = job_description_data  # Store data in session state
                    st.success("Job description extracted successfully.")

                    # Convert job description data to DataFrame for display
                    # df = pd.DataFrame.from_dict([job_description_data])  # Wrap in list if single dictionary
                    # st.dataframe(df)  # Display data as table
                else:
                    st.error(f"Failed to extract job description. Status code: {response.status_code}")
                    st.error(f"Error message: {response.text}")

    # Display the parsed job description data if it exists
    if "job_description_data" in st.session_state:
        st.subheader("Parsed Job Description Data")
        df = pd.DataFrame.from_dict([st.session_state.job_description_data])
        st.dataframe(df)  # Always display the parsed job description

        # Embedding-based search option
        st.subheader("Embedding-Based Candidate Search")

        # Button to search candidates based on job description
        if st.button("Search Candidates with Embeddings"):
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
                    # Display results
                    st.success(f"Found {len(candidates)} candidates.")
                    df = pd.DataFrame(candidates)
                    st.dataframe(df)
                else:
                    st.warning("No candidates found.")
            else:
                st.error(f"Failed to search candidates. Status code: {search_response.status_code}")
                st.error(f"Error message: {search_response.text}")
