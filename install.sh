
## 01. run backend source


## install env
cd /Users/giangvo/Desktop/01-projects/p04-cv-screening/project
conda env create -f env.yml
conda activate cv-screening

## init database
python database_init.py

cd p04-cv-screening/project/backend
/Users/giangvo/miniconda3/envs/cv-screening/bin/uvicorn main:app --reload


## create account
http://127.0.0.1:8000/docs#/default/create_user_auth_users__post


user_name: giangvt6
pw: giangvt6


## start Frontend
conda activate cv-screening
cd /Users/giangvo/Desktop/01-projects/p04-cv-screening/project/frontend/
streamlit run app.py





