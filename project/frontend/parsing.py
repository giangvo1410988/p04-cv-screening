
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

    # response = requests.get(f"{API_URL}/files?folder_id={folder_id}", headers={"Authorization": f"Bearer {st.session_state.token}"})
    # if response.status_code == 200:
    #     files = response.json()
    #     if files:
    #         df = pd.DataFrame(files)
    #         df['Select'] = False
    #         columns = ['Select', 'id', 'filename'] + [col for col in df.columns if col not in ['Select', 'id', 'filename']]
    #         df = df[columns]
            
    #         edited_df = st.data_editor(
    #             df,
    #             hide_index=True,
    #             column_config={
    #                 "Select": st.column_config.CheckboxColumn(required=True),
    #                 "filename": st.column_config.TextColumn(
    #                     "Filename",
    #                     help="File name",
    #                     required=True,
    #                 ),
    #             },
    #             disabled=df.columns.drop(['Select']),
    #             key="file_table"
    #         )
                
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
    print("\n\n\n")
    print("==> data: ", data)

    # Prepare data for the table
    table_data = []
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

            # Add education, certificates, projects, and awards as JSON strings
            row["Education"] = json.dumps(parsed_data.get('education', [])) if parsed_data.get('education') is not None else ''
            row["Certificates"] = json.dumps(parsed_data.get('certificates', {})) if parsed_data.get('certificates') is not None else ''
            row["Projects"] = json.dumps(parsed_data.get('projects', [])) if parsed_data.get('projects') is not None else ''
            row["Awards"] = json.dumps(parsed_data.get('awards', [])) if parsed_data.get('awards') is not None else ''
        else:  # Handle cases where parsed_data is None
            row["Skills"] = ""
            row["Objectives"] = ""
            row["Education"] = ""
            row["Certificates"] = ""
            row["Projects"] = ""
            row["Awards"] = ""

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
