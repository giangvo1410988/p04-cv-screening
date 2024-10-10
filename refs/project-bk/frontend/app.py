import streamlit as st
import requests
import json
import pandas as pd
import base64

API_URL = "http://localhost:8000"  # Adjust this to your FastAPI backend URL

def login():
    st.title("CV Screening - Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
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
        for folder in folders:
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                if st.button(f"{folder['name']} ({folder['num_files']} files, {folder['size']} bytes)", key=f"folder_{folder['id']}"):
                    st.session_state.current_folder = folder['id']
                    st.session_state.current_folder_name = folder['name']
                    st.rerun()
            with col2:
                if st.button("Delete", key=f"delete_{folder['id']}"):
                    delete_folder(folder['id'])
    else:
        st.error("Failed to fetch folders")

def delete_folder(folder_id):
    response = requests.delete(f"{API_URL}/folders/{folder_id}", headers={"Authorization": f"Bearer {st.session_state.token}"})
    if response.status_code == 204:
        st.success("Folder deleted successfully!")
        st.rerun()
    else:
        st.error("Failed to delete folder")

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
        elif response.status_code == 400:
            try:
                error_detail = response.json()['detail']
                if 'uploaded_files' in error_detail:
                    if error_detail['uploaded_files']:
                        st.success(f"Successfully uploaded: {', '.join([file['filename'] for file in error_detail['uploaded_files']])}")
                if 'duplicate_files' in error_detail:
                    st.warning(f"Duplicate files not uploaded: {', '.join(error_detail['duplicate_files'])}")
                if 'invalid_files' in error_detail:
                    st.error(f"Invalid files not uploaded: {', '.join(error_detail['invalid_files'])}")
            except json.JSONDecodeError:
                st.error(f"Failed to upload files: {response.text}")
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

def view_file(file_id, filename):
    response = requests.get(
        f"{API_URL}/files/{file_id}/download",
        headers={"Authorization": f"Bearer {st.session_state.token}"},
        stream=True
    )
    if response.status_code == 200:
        pdf_content = response.content
        base64_pdf = base64.b64encode(pdf_content).decode('utf-8')
        pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="700" height="1000" type="application/pdf"></iframe>'
        st.markdown(pdf_display, unsafe_allow_html=True)
    else:
        st.error("Failed to fetch the file")

def list_files(folder_id):
    response = requests.get(f"{API_URL}/files?folder_id={folder_id}", headers={"Authorization": f"Bearer {st.session_state.token}"})
    if response.status_code == 200:
        files = response.json()
        if files:
            df = pd.DataFrame(files)
            
            # Add a checkbox column to the dataframe
            df['Select'] = False
            
            # Reorder columns to make 'Select' the first column
            columns = ['Select', 'id', 'filename'] + [col for col in df.columns if col not in ['Select', 'id', 'filename']]
            df = df[columns]
            
            # Use st.data_editor for an editable dataframe with checkboxes
            edited_df = st.data_editor(
                df,
                hide_index=True,
                column_config={
                    "Select": st.column_config.CheckboxColumn(required=True),
                    "filename": st.column_config.Column(
                        "Filename",
                        help="Click to view the file",
                        required=True,
                    ),
                },
                disabled=df.columns.drop(['Select', 'filename']),
                key="file_table"
            )
            
            # Get the IDs of selected files
            selected_file_ids = edited_df[edited_df['Select']]['id'].tolist()
            
            # Add a delete button for selected files
            if st.button("Delete Selected Files"):
                if selected_file_ids:
                    delete_files(selected_file_ids)
                else:
                    st.warning("No files selected for deletion.")
            
            # Check if a file was clicked
            if st.session_state.file_table is not None:
                clicked_row = st.session_state.file_table["edited_rows"]
                if clicked_row:
                    row_index = list(clicked_row.keys())[0]
                    clicked_file = edited_df.iloc[row_index]
                    if clicked_file['filename'] != df.iloc[row_index]['filename']:
                        st.subheader(f"Viewing file: {clicked_file['filename']}")
                        view_file(clicked_file['id'], clicked_file['filename'])
        else:
            st.info("No files in this folder yet.")
    else:
        st.error("Failed to fetch files")

def main():
    st.set_page_config(page_title="CV Screening", page_icon="📄", layout="wide")
    
    if "token" not in st.session_state:
        login()
    else:
        st.sidebar.title("CV Screening")
        if st.sidebar.button("Back to Folders"):
            st.session_state.pop('current_folder', None)
            st.session_state.pop('current_folder_name', None)
            st.rerun()

        if "current_folder" not in st.session_state:
            list_folders()
            create_folder()
        else:
            st.title(f"CV Screening - Folder: {st.session_state.current_folder_name}")
            
            # Pinned upload section
            with st.container():
                st.markdown("---")
                upload_files(st.session_state.current_folder)
                st.markdown("---")
            
            # Scrollable file list with checkboxes
            st.subheader("Files in Folder")
            list_files(st.session_state.current_folder)

if __name__ == "__main__":
    main()

