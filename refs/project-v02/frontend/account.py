import streamlit as st
from streamlit_lottie import st_lottie
import requests
from config import API_URL

def load_lottieurl(url: str):
    r = requests.get(url)
    if r.status_code != 200:
        return None
    return r.json()

def login():
    st.title("CV Screening - Login")
    
    # Page layout
    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown('<p class="big-font">CV Screening</p>', unsafe_allow_html=True)
        st.write("Welcome back! Please login to your account.")
        
        # Load and display the Lottie animation
        lottie_url = "https://assets5.lottiefiles.com/packages/lf20_jcikwtux.json"
        lottie_json = load_lottieurl(lottie_url)
        if lottie_json:
            st_lottie(lottie_json, height=300)

    with col2:
        st.write("")
        st.write("")
        with st.form("login_form"):
            username = st.text_input("Username", placeholder="Enter your username")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            submit_button = st.form_submit_button(label="Login")
        
        if submit_button:
            if username and password:
                response = requests.post(f"{API_URL}/auth/token", data={"username": username, "password": password})
                if response.status_code == 200:
                    st.session_state.token = response.json()["access_token"]
                    st.success("Logged in successfully!")
                    st.balloons()
                    st.rerun()
                else:
                    st.error("Invalid username or password")
            else:
                st.warning("Please enter both username and password")

        st.write("")
        st.write("Don't have an account? [Sign up here]()")
