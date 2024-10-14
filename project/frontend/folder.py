from config import API_URL
import requests
import streamlit as st
import base64
import pandas as pd
from parsing import check_folder_status

def folder_title(folder_name):
    ## Layout
    col1, col2, col3 = st.columns([3, 2, 1])
    with col1:
        st.title(f"{folder_name}")
    with col3:
        # Add "Back to Folders" button
        if st.button("Back to Folders"):
            del st.session_state.current_folder
            del st.session_state.current_folder_name
            st.rerun()
    # st.markdown("---")
def list_and_preview_file(folder_id):
    st.subheader("List of cv's candidates")
    response = requests.get(f"{API_URL}/files?folder_id={folder_id}", headers={"Authorization": f"Bearer {st.session_state.token}"})
    if response.status_code == 200:
        files = response.json()
        if files:
            df = pd.DataFrame(files)
            df['Select'] = False
            columns = ['Select', 'id', 'filename'] + [col for col in df.columns if col not in ['Select', 'id', 'filename']]
            df = df[columns]
            
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

            col1, col2, _ = st.columns([1, 1, 2])
            with col1:
                if st.button("Delete Selected Files"):
                    if selected_file_ids:
                        delete_files(selected_file_ids)
                    else:
                        st.warning("No files selected for deletion.")
            
            with col2:
                if st.button("Preview Selected File"):
                    if len(selected_file_ids) == 1:
                        st.session_state.current_file = selected_file_ids[0]
                        st.session_state.current_filename = edited_df[edited_df['id'] == selected_file_ids[0]]['filename'].values[0]
                        st.rerun()
                    elif len(selected_file_ids) > 1:
                        st.warning("Please select only one file for preview.")
                    else:
                        st.warning("No file selected for preview.")

            ## preview part
            st.subheader("Preview")

            # Default to the first file if no file is selected
            if 'current_file' not in st.session_state and not edited_df.empty:
                st.session_state.current_file = edited_df.iloc[0]['id']
                st.session_state.current_filename = edited_df.iloc[0]['filename']

            if 'current_file' in st.session_state:
                pdf_display = view_file(st.session_state.current_file, st.session_state.current_filename)
                if pdf_display:
                    st.markdown(pdf_display, unsafe_allow_html=True)
                else:
                    st.error("Failed to load the file preview.")
            else:
                st.info("No files available for preview.")
        else:
            st.info("No files in this folder yet.")
    else:
        st.error("Failed to fetch files")
##

def upload_file(folder_id):
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

def list_folders():
    # Fetch folders
    response = requests.get(f"{API_URL}/folders", headers={"Authorization": f"Bearer {st.session_state.token}"})
    if response.status_code != 200:
        st.error("Failed to fetch folders")
        return

    folders = response.json()

    ## Layout
    col1, col2 = st.columns([3, 1])
    with col1:
        st.title("CV Screening - Your Candidates")

    with col2:
        folder_name = st.text_input("", placeholder="Enter folder name")
        create_button = st.button("Create Folder")
        
        if create_button:
            if folder_name:
                response = requests.post(
                    f"{API_URL}/folders",
                    json={"name": folder_name},
                    headers={"Authorization": f"Bearer {st.session_state.token}"}
                )
                if response.status_code == 200:
                    st.success("Folder created successfully!")
                    st.rerun()
                else:
                    st.error("Failed to create folder")
            else:
                st.warning("Please enter a folder name")
    st.markdown("---")

    if not folders:
        st.info("You don't have any folders yet. Create one to get started!")
    else:
        for folder in folders:
            with st.container():
                col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                with col1:
                    st.markdown(f"### 📁 {folder['name']}")
                    st.caption(f"{folder['num_files']} files | {folder['size']} bytes")
                    
                    # Call check_folder_status to display the parsing status
                    check_folder_status(folder['id'])

                    status_response = requests.get(
                        f"{API_URL}/folders/{folder['id']}/status-summary?service_name=cv_parsing&folder_name={folder['name']}",
                        headers={"Authorization": f"Bearer {st.session_state.token}"}
                    )
                    if status_response.status_code == 200:
                        status_summary = status_response.json().get("status_summary", "")
                        st.text(status_summary)
                    else:
                        st.warning("Not Parsing Data Yet")
                with col2:
                    if st.button("Open", key=f"open_{folder['id']}"):
                        st.session_state.current_folder = folder['id']
                        st.session_state.current_folder_name = folder['name']
                        st.rerun()
                with col3:
                    if st.button("Delete", key=f"delete_{folder['id']}"):
                        if delete_folder(folder['id']):
                            st.success(f"Folder '{folder['name']}' deleted successfully!")
                            st.rerun()
                st.markdown("---")



def delete_folder(folder_id):
    response = requests.delete(
        f"{API_URL}/folders/{folder_id}",
        headers={"Authorization": f"Bearer {st.session_state.token}"}
    )
    return response.status_code == 200

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
        pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="600" type="application/pdf"></iframe>'
        return pdf_display
    else:
        return None