
psycopg2

## init database
python database_init.py
    Existing database 'cvscreening' dropped.
    Existing user 'cvscreening_user' dropped.
    User 'cvscreening_user' created.
    Database 'cvscreening' created.
    Privileges granted to 'cvscreening_user'.
    All tables created successfully!


## 
sqlalchemy
fastapi, sqlalchemy, passlib, python-jose

Run the FastAPI server 
uvicorn main:app --reload

pip install --upgrade fastapi uvicorn[standard] pydantic

## go to source folder
cd /Users/giangvo/Desktop/01-projects/p04-cv-screening/project
conda env create -f env.yml
conda activate cv-screening

python database_init.py

## run main source
cd /Users/giangvo/Desktop/01-projects/p04-cv-screening/project/backend
/Users/giangvo/miniconda3/envs/cv-screening/bin/uvicorn main:app --reload 

pip install python-multipart
pip install bcrypt

## create account
http://127.0.0.1:8000/docs#/default/create_user_auth_users__post

user_name: giangvt6
pw: giangvt6

pip install email-validator
pip install streamlit requests pandas
pip install python-magic python-docx2txt PyPDF2 langdetect
pip install python-magic-bin # for mac
pip install python-magic

## start Frontend
conda activate cv-screening
cd /Users/giangvo/Desktop/01-projects/p04-cv-screening/project/frontend/
streamlit run app.py

PyPDF2
pip install scikit-learn
pip install streamlit_option_menu

pip install plotly

pip install openpyxl
pip install openai

pip install streamlit_lottie


