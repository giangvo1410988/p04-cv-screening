
import streamlit as st
import requests
import json
import pandas as pd
import base64
import plotly.express as px
from config import API_URL
import time


def ai_parsing(folder_id):
    st.subheader("AI Parsing")

    if st.button("Start Parsing"):
        parse_folder(folder_id)

    if st.button("Check Parsing Status"):
        check_folder_status(folder_id)
    status_response = requests.get(
        f"{API_URL}/folders/{folder_id}/idsummary",
        headers={"Authorization": f"Bearer {st.session_state.token}"}
    )
    if status_response.status_code == 200:
        status_summary = status_response.json().get("status_summary", "")
        st.success(status_summary)
    else:
        st.warning("Not Parsing Data Yet")
    # st.markdown("---")

def parse_folder(folder_id):
    with st.spinner("Starting parsing process..."):
        response = requests.post(
            f"{API_URL}/parsing/{folder_id}/parse",
            headers={"Authorization": f"Bearer {st.session_state.token}"}
        )
        if response.status_code == 200:
            st.success("Parsing started successfully.")
            
            check_folder_status(folder_id)
            # Load the returned data
            data = response.json()
            
            # Display parsed data
            display_parsed_data(data)
            
            # Option to download the full data as JSON
            json_str = json.dumps(data, indent=2)
            b64 = base64.b64encode(json_str.encode()).decode()
            href = f'<a href="data:file/json;base64,{b64}" download="parsed_data.json">Download JSON File</a>'
            st.markdown(href, unsafe_allow_html=True)
        else:
            st.error(f"Failed to start parsing. Status code: {response.status_code}")
            st.error(f"Error message: {response.text}")

def check_folder_status(folder_id):
    url = f"{API_URL}/folders/{folder_id}/status"
    response = requests.get(
        url,
        headers={"Authorization": f"Bearer {st.session_state.token}"}
    )
    if response.status_code == 200:
        job = response.json()
        if job["status"] == "parsing":
            st.info("AI Parsing is in progress")
        elif job["status"] == "parsed_complete":
            st.success("Folder was parsed completely")
        elif job["status"] == "parsed_apart":
            st.warning("Folder parsed but there are some files that could not be completed")
    else:
        st.error("No parsing data found")



def display_parsed_data(data):
    print("\n\n\n")
    print("==> data: ", data)

    # Prepare data for the file overview table
    table_data = []
    education_data = []
    certificates_data = []
    projects_data = []
    awards_data = []

    for cv in data:
        # Handle the possibility of None values
        row = {
            "Filename": cv.get('filename', ''),
            "Status": cv.get('status', ''),
            "File Type": cv.get('file_type', ''),
            "Size (bytes)": cv.get('size', ''),
            "Words": cv.get('words', ''),
            "Pages": cv.get('number_page', ''),
            "Language": cv.get('language', ''),
            "Uploaded Date": cv.get('uploaded_date', ''),
        }

        parsed_data = cv.get('parsed_data', None)
        if parsed_data:  # Only process if parsed_data is not None
            personal_info = parsed_data.get('personal_information', {})
            for key, value in personal_info.items():
                row[f"Personal Info - {key.capitalize()}"] = value if value is not None else ''

            row["Skills"] = ", ".join(parsed_data.get('skills', [])) if parsed_data.get('skills') is not None else ''
            row["Objectives"] = parsed_data.get('objectives', '')

            # Extract education, certificates, projects, and awards data
            education_data.extend(parsed_data.get('education', []))
            certificates_data.extend(parsed_data.get('certificates', {}).get('language_certificates', []))
            certificates_data.extend(parsed_data.get('certificates', {}).get('other_certificates', []))
            projects_data.extend(parsed_data.get('projects', []))
            awards_data.extend(parsed_data.get('awards', []))

        table_data.append(row)

    # Create and display the file overview dataframe
    df = pd.DataFrame(table_data)
    st.dataframe(df, use_container_width=True)

    # Display Education Table
    if education_data:
        st.subheader("Education")
        df_education = pd.DataFrame(education_data)
        st.dataframe(df_education, use_container_width=True)

    # Display Certificates Table
    if certificates_data:
        st.subheader("Certificates")
        df_certificates = pd.DataFrame(certificates_data)
        st.dataframe(df_certificates, use_container_width=True)

    # Display Projects Table
    if projects_data:
        st.subheader("Projects")
        df_projects = pd.DataFrame(projects_data)
        st.dataframe(df_projects, use_container_width=True)

    # Display Awards Table
    if awards_data:
        st.subheader("Awards")
        df_awards = pd.DataFrame(awards_data)
        st.dataframe(df_awards, use_container_width=True)

    # Option to download all data as CSV
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="parsed_cv_data.csv">Download CSV File</a>'
    st.markdown(href, unsafe_allow_html=True)

    # Option to download parsed education data
    if education_data:
        csv_education = pd.DataFrame(education_data).to_csv(index=False)
        b64_education = base64.b64encode(csv_education.encode()).decode()
        href_education = f'<a href="data:file/csv;base64,{b64_education}" download="education_data.csv">Download Education Data CSV</a>'
        st.markdown(href_education, unsafe_allow_html=True)

    # Option to download parsed certificates data
    if certificates_data:
        csv_certificates = pd.DataFrame(certificates_data).to_csv(index=False)
        b64_certificates = base64.b64encode(csv_certificates.encode()).decode()
        href_certificates = f'<a href="data:file/csv;base64,{b64_certificates}" download="certificates_data.csv">Download Certificates Data CSV</a>'
        st.markdown(href_certificates, unsafe_allow_html=True)

    # Option to download parsed projects data
    if projects_data:
        csv_projects = pd.DataFrame(projects_data).to_csv(index=False)
        b64_projects = base64.b64encode(csv_projects.encode()).decode()
        href_projects = f'<a href="data:file/csv;base64,{b64_projects}" download="projects_data.csv">Download Projects Data CSV</a>'
        st.markdown(href_projects, unsafe_allow_html=True)

    # Option to download parsed awards data
    if awards_data:
        csv_awards = pd.DataFrame(awards_data).to_csv(index=False)
        b64_awards = base64.b64encode(csv_awards.encode()).decode()
        href_awards = f'<a href="data:file/csv;base64,{b64_awards}" download="awards_data.csv">Download Awards Data CSV</a>'
        st.markdown(href_awards, unsafe_allow_html=True)


def check_parsing_status(folder_id):
    if not st.session_state.get('parsing_started', False):
        st.info("Click 'Start Parsing' to begin the parsing process.")
        return

    parsing_complete = False
    progress_bar = st.progress(0)
    status_text = st.empty()

    while not parsing_complete:
        response = requests.get(
            f"{API_URL}/parsing/{folder_id}/status",
            headers={"Authorization": f"Bearer {st.session_state.token}"}
        )
        if response.status_code == 200:
            files = response.json()
            statuses = [file['status'] for file in files]
            total = len(statuses)
            parsed = statuses.count("parsed")
            parsing = statuses.count("parsing")
            unparsed = statuses.count("unparsed")
            
            progress = parsed / total if total != 0 else 0
            progress_bar.progress(progress)
            status_text.text(f"Parsed: {parsed}/{total}")

            if parsed == total:
                parsing_complete = True
            else:
                time.sleep(5)  # Wait for 5 seconds before checking again
        else:
            st.error(f"Failed to fetch parsing status. Status code: {response.status_code}")
            st.error(f"Error message: {response.text}")
            break

    if parsing_complete:
        st.success("All files parsed successfully!")
        display_cv_info(folder_id)

def display_cv_info(folder_id):
    st.subheader("CV Information")
    with st.spinner("Fetching CV information..."):
        response = requests.get(
            f"{API_URL}/parsing/{folder_id}/cv_info",
            headers={"Authorization": f"Bearer {st.session_state.token}"}
        )
        if response.status_code == 200:
            cv_info = response.json()
            if cv_info:
                display_parsed_data(cv_info)
            else:
                st.warning("No CV information available. The parsing result might be empty.")
        else:
            st.error(f"Failed to fetch CV information. Status code: {response.status_code}")
            st.error(f"Error message: {response.text}")
