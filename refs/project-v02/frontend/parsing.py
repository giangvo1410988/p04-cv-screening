
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
    # st.markdown("---")
        
def parse_folder(folder_id):
    with st.spinner("Starting parsing process..."):
        response = requests.post(
            f"{API_URL}/parsing/{folder_id}/parse",
            headers={"Authorization": f"Bearer {st.session_state.token}"}
        )
        if response.status_code == 200:
            st.success("Parsing completed successfully.")
            
            # Load the returned data
            data = response.json()
            
            # Display parsed data
            display_parsed_data(data)
            
            # Option to download the full data as JSON
            json_str = json.dumps(data, indent=2)
            b64 = base64.b64encode(json_str.encode()).decode()
            href = f'<a href="data:file/json;base64,{b64}" download="parsed_data.json">Download JSON File</a>'
            st.markdown(href, unsafe_allow_html=True)
            
            st.session_state.parsing_started = True
        else:
            st.error(f"Failed to start parsing. Status code: {response.status_code}")
            st.error(f"Error message: {response.text}")

def display_parsed_data(data):
    # Prepare data for the table
    table_data = []
    for cv in data:
        row = {
            "Filename": cv['filename'],
            "Status": cv['status'],
            "File Type": cv['file_type'],
            "Size (bytes)": cv['size'],
            "Words": cv['words'],
            "Pages": cv['number_page'],
            "Language": cv['language'],
            "Uploaded Date": cv['uploaded_date'],
        }
        
        parsed_data = cv['parsed_data']
        personal_info = parsed_data.get('personal_information', {})
        for key, value in personal_info.items():
            row[f"Personal Info - {key.capitalize()}"] = value
        
        row["Skills"] = ", ".join(parsed_data.get('skills', []))
        row["Objectives"] = parsed_data.get('objectives', '')
        
        # Add education, certificates, projects, and awards as JSON strings
        # (You may want to process these differently depending on your needs)
        row["Education"] = json.dumps(parsed_data.get('education', []))
        row["Certificates"] = json.dumps(parsed_data.get('certificates', {}))
        row["Projects"] = json.dumps(parsed_data.get('projects', []))
        row["Awards"] = json.dumps(parsed_data.get('awards', []))
        
        table_data.append(row)
    
    # Create and display the dataframe
    df = pd.DataFrame(table_data)
    st.dataframe(df)
    
    # Option to download as CSV
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="parsed_cv_data.csv">Download CSV File</a>'
    st.markdown(href, unsafe_allow_html=True)

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
