import streamlit as st
import requests
import json
import pandas as pd
import base64
from io import BytesIO
from streamlit_option_menu import option_menu
import plotly.express as px

API_URL = "http://localhost:8000"  # Adjust this to your FastAPI backend URL

def set_page_config():
    st.set_page_config(page_title="CV Screening", page_icon="📄", layout="wide")
    st.markdown("""
        <style>
        .main {
            padding-top: 2rem;
        }
        .stButton>button {
            width: 100%;
        }
        .stDataFrame {
            font-size: 14px;
        }
        </style>
        """, unsafe_allow_html=True)

def login():
    st.title("CV Screening - Login")
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login", key="login_button"):
            response = requests.post(f"{API_URL}/auth/token", data={"username": username, "password": password})
            if response.status_code == 200:
                st.session_state.token = response.json()["access_token"]
                st.success("Logged in successfully!")
                st.rerun()
            else:
                st.error("Invalid username or password")

def list_folders():
    st.title("CV Screening - Your Candidates")
    response = requests.get(f"{API_URL}/folders", headers={"Authorization": f"Bearer {st.session_state.token}"})
    if response.status_code == 200:
        folders = response.json()
        col1, col2 = st.columns([3, 1])
        with col1:
            for folder in folders:
                if st.button(f"📁 {folder['name']} ({folder['num_files']} files, {folder['size']} bytes)", key=f"folder_{folder['id']}"):
                    st.session_state.current_folder = folder['id']
                    st.session_state.current_folder_name = folder['name']
                    st.rerun()
        with col2:
            create_folder()

def create_folder():
    st.subheader("Create New Folder")
    folder_name = st.text_input("Folder Name")
    if st.button("Create Folder"):
        response = requests.post(f"{API_URL}/folders", json={"name": folder_name}, headers={"Authorization": f"Bearer {st.session_state.token}"})
        if response.status_code == 200:
            st.success("Folder created successfully!")
            st.rerun()
        else:
            st.error("Failed to create folder")

def upload_files(folder_id):
    st.subheader("Upload Files")
    uploaded_files = st.file_uploader("Choose PDF files", accept_multiple_files=True, type=['pdf'])
    if uploaded_files and st.button("Upload Files"):
        files = [("files", file) for file in uploaded_files]
        with st.spinner("Uploading files..."):
            response = requests.post(
                f"{API_URL}/files?folder_id={folder_id}",
                files=files,
                headers={"Authorization": f"Bearer {st.session_state.token}"}
            )
        
        if response.status_code == 200:
            result = response.json()
            uploaded_files = [file['filename'] for file in result['uploaded_files']]
            duplicate_files = result['duplicate_files']
            invalid_files = result['invalid_files']
            
            if uploaded_files:
                st.success(f"Successfully uploaded: {', '.join(uploaded_files)}")
            if duplicate_files:
                st.warning(f"Duplicate files not uploaded: {', '.join(duplicate_files)}")
            if invalid_files:
                st.error(f"Invalid files not uploaded: {', '.join(invalid_files)}")
            
            if uploaded_files:
                st.rerun()
        else:
            st.error(f"Failed to upload files: {response.text}")

def delete_files(file_ids):
    for file_id in file_ids:
        response = requests.delete(
            f"{API_URL}/files/{file_id}",
            headers={"Authorization": f"Bearer {st.session_state.token}"}
        )
        if response.status_code != 204:
            st.error(f"Failed to delete file with ID {file_id}")
            return
    
    st.success("Successfully deleted files!")
    st.rerun()

import streamlit as st
import requests
import json
import pandas as pd
import base64
from io import BytesIO
from streamlit_option_menu import option_menu
import plotly.express as px


import streamlit as st
import requests
import json
import pandas as pd
import base64
from io import BytesIO
from streamlit_option_menu import option_menu
import plotly.express as px


def view_file(file_id, filename):
    response = requests.get(
        f"{API_URL}/files/{file_id}/download",
        headers={"Authorization": f"Bearer {st.session_state.token}"},
        stream=True
    )
    if response.status_code == 200:
        pdf_content = response.content
        base64_pdf = base64.b64encode(pdf_content).decode('utf-8')
        pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="600" type="application/pdf"></iframe>'
        return pdf_display
    else:
        return None

def list_files(folder_id):
    response = requests.get(f"{API_URL}/files?folder_id={folder_id}", headers={"Authorization": f"Bearer {st.session_state.token}"})
    if response.status_code == 200:
        files = response.json()
        if files:
            df = pd.DataFrame(files)
            df['Select'] = False
            columns = ['Select', 'id', 'filename'] + [col for col in df.columns if col not in ['Select', 'id', 'filename']]
            df = df[columns]
            
            st.subheader("File List")
            edited_df = st.data_editor(
                df,
                hide_index=True,
                column_config={
                    "Select": st.column_config.CheckboxColumn(required=True),
                    "filename": st.column_config.TextColumn(
                        "Filename",
                        help="File name",
                        required=True,
                    ),
                },
                disabled=df.columns.drop(['Select']),
                key="file_table"
            )
            
            selected_file_ids = edited_df[edited_df['Select']]['id'].tolist()
            
            if st.button("Delete Selected Files"):
                if selected_file_ids:
                    delete_files(selected_file_ids)
                else:
                    st.warning("No files selected for deletion.")
            
            # File viewing section
            st.subheader("View Files")
            col1, col2 = st.columns([1, 3])
            
            with col1:
                st.subheader("File Names")
                for index, row in edited_df.iterrows():
                    if st.button(f"{row['filename']}", key=f"view_{row['id']}"):
                        st.session_state.current_file = row['id']
                        st.session_state.current_filename = row['filename']
                        st.rerun()
            
            with col2:
                st.subheader("File Preview")
                if 'current_file' in st.session_state:
                    pdf_display = view_file(st.session_state.current_file, st.session_state.current_filename)
                    if pdf_display:
                        st.markdown(pdf_display, unsafe_allow_html=True)
                    else:
                        st.error("Failed to load the file preview.")
                else:
                    st.info("Select a file to preview.")
        else:
            st.info("No files in this folder yet.")
    else:
        st.error("Failed to fetch files")

def parse_folder(folder_id):
    st.subheader("AI Parsing")
    if st.button("Start Parsing"):
        response = requests.post(
            f"{API_URL}/parsing/{folder_id}/parse",
            headers={"Authorization": f"Bearer {st.session_state.token}"}
        )
        if response.status_code == 200:
            st.success("Parsing started. Check status for updates.")
        else:
            st.error("Failed to start parsing")

def check_parsing_status(folder_id):
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
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total files", total)
            st.metric("Parsed", parsed)
            st.metric("Parsing", parsing)
            st.metric("Unparsed", unparsed)
        
        with col2:
            fig = px.pie(values=[parsed, parsing, unparsed], names=['Parsed', 'Parsing', 'Unparsed'], title='Parsing Status')
            st.plotly_chart(fig, use_container_width=True)
        
        if parsed == total:
            st.success("All files parsed successfully!")
            if st.button("Download Parsed Data"):
                download_parsed_data(folder_id)
    else:
        st.error("Failed to fetch parsing status")

def download_parsed_data(folder_id):
    response = requests.get(
        f"{API_URL}/parsing/{folder_id}/download",
        headers={"Authorization": f"Bearer {st.session_state.token}"}
    )
    if response.status_code == 200:
        st.download_button(
            label="Download Excel",
            data=response.content,
            file_name=f"parsed_data_{st.session_state.current_folder_name}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.error("Failed to download parsed data")

def cv_scoring(folder_id):
    st.subheader("CV Scoring")
    score_method = st.radio("Choose job description input method:", ("Upload PDF", "Type or Paste"))
    
    if score_method == "Upload PDF":
        uploaded_file = st.file_uploader("Upload job description PDF", type=['pdf'])
        if uploaded_file:
            files = {"job_description_file": uploaded_file}
            data = {}
        else:
            st.warning("Please upload a PDF file")
            return
    else:
        job_description = st.text_area("Enter job description")
        if job_description:
            files = None
            data = {"job_description": job_description}
        else:
            st.warning("Please enter a job description")
            return
    
    if st.button("Score CVs"):
        response = requests.post(
            f"{API_URL}/scoring/{folder_id}/score",
            headers={"Authorization": f"Bearer {st.session_state.token}"},
            files=files,
            data=data
        )
        if response.status_code == 200:
            scores = response.json()
            df = pd.DataFrame(scores)
            st.dataframe(df)
            
            fig = px.bar(df, x='filename', y='score', title='CV Scores')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.error("Failed to score CVs")

def main():
    set_page_config()
    
    if "token" not in st.session_state:
        login()
    else:
        with st.sidebar:
            st.title("CV Screening")
            menu_choice = option_menu(
                "Main Menu",
                ["Folders", "Upload", "Files", "AI Parsing", "CV Scoring"],
                icons=['folder', 'cloud-upload', 'file-earmark', 'cpu', 'star'],
                menu_icon="cast",
                default_index=0,
            )
        
        if menu_choice == "Folders" or "current_folder" not in st.session_state:
            list_folders()
        elif "current_folder" in st.session_state:
            st.title(f"CV Screening - Folder: {st.session_state.current_folder_name}")
            
            if menu_choice == "Upload":
                upload_files(st.session_state.current_folder)
            elif menu_choice == "Files":
                list_files(st.session_state.current_folder)
            elif menu_choice == "AI Parsing":
                parse_folder(st.session_state.current_folder)
                check_parsing_status(st.session_state.current_folder)
            elif menu_choice == "CV Scoring":
                cv_scoring(st.session_state.current_folder)

if __name__ == "__main__":
    main()