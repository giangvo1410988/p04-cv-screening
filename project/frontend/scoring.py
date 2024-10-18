# import streamlit as st
# import requests
# import pandas as pd
# import base64


# API_URL = "http://localhost:8002"  # Adjust this to your FastAPI backend URL


# def cv_scoring(folder_id):
#     # CV Scoring section
#     st.subheader("CV Scoring")
#     score_method = st.radio("Choose job description input method:", ("Upload PDF", "Type or Paste"))

#     if score_method == "Upload PDF":
#         uploaded_file = st.file_uploader("Upload job description PDF", type=['pdf'])
#         if uploaded_file:
#             files = {"job_description_file": uploaded_file}
#             data = {}
#         else:
#             st.warning("Please upload a PDF file")
#             return
#     else:
#         job_description = st.text_area("Enter job description")
#         if job_description:
#             files = None
#             data = {"job_description": job_description}
#         else:
#             st.warning("Please enter a job description")
#             return

#     if st.button("Score CVs"):
#         matching(folder_id, files, data)

# def matching(folder_id, files, data):
#     with st.spinner("Scoring CVs..."):
#         response = requests.post(
#             f"{API_URL}/scoring/{folder_id}/score",
#             headers={"Authorization": f"Bearer {st.session_state.token}"},
#             files=files,
#             data=data
#         )
#         if response.status_code == 200:
#             scores = response.json()
#             df = pd.DataFrame(scores)
#             st.dataframe(df)
            
#             fig = px.bar(df, x='filename', y='score', title='CV Scores')
#             st.plotly_chart(fig, use_container_width=True)
            
#             # Option to download scores as CSV
#             csv = df.to_csv(index=False)
#             b64 = base64.b64encode(csv.encode()).decode()
#             href = f'<a href="data:file/csv;base64,{b64}" download="cv_scores.csv">Download CSV File</a>'
#             st.markdown(href, unsafe_allow_html=True)
#         else:
#             st.error(f"Failed to score CVs. Status code: {response.status_code}")
#             st.error(f"Error message: {response.text}")
