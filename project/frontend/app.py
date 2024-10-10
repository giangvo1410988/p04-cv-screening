import streamlit as st
import requests
import json
from io import BytesIO
from streamlit_option_menu import option_menu
import plotly.express as px
import time

# import developed components
from config import API_URL
from init import set_page_config
from account import login 
import folder
import parsing
import scoring

def folder_view(folder_id, folder_name):
    folder.folder_title(folder_name)
    st.markdown("---")

    folder.upload_file(folder_id)
    st.markdown("---")

    folder.list_and_preview_file(folder_id)
    st.markdown("---")

    parsing.ai_parsing(folder_id)
    st.markdown("---")

    scoring.cv_scoring(folder_id)
    st.markdown("---")

def main():
    set_page_config()

    # Initialize session state for file selection
    if "selected_file_id" not in st.session_state:
        st.session_state.selected_file_id = None

    if "token" not in st.session_state:
        login()
    else:
        with st.sidebar:
            st.markdown("<h1 style='text-align: center;'>AI Screening App</h1>", unsafe_allow_html=True)
            menu_choice = option_menu(
                "Main Menu",
                ["Folders"],
                icons=['folder'],
                menu_icon="cast",
                default_index=0,
            ) 
        
        if menu_choice == "Folders":
            if "current_folder" in st.session_state:
                folder_view(st.session_state.current_folder, st.session_state.current_folder_name)
            else:
                folder.list_folders()

if __name__ == "__main__":
    main()

    