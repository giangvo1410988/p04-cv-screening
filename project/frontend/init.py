import streamlit as st

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
        .big-font {
            font-size:30px !important;
            font-weight: bold;
            color: #1E88E5;
        }
        .create-folder-container {
            background-color: #f0f2f6;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            margin-bottom: 20px;
        }
        .create-folder-title {
            color: #1E88E5;
            font-size: 20px;
            font-weight: bold;
            margin-bottom: 15px;
        }
        </style>
        """, unsafe_allow_html=True)