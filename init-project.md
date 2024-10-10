I'd be happy to provide you with the code structure for the website you've described. This will involve creating a FastAPI backend, a PostgreSQL database, and a Streamlit frontend. Let's break this down into different components.

```plaintext
project/
├── backend/
│   ├── main.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   └── routers/
│       ├── auth.py
│       ├── folders.py
│       └── files.py
├── frontend/
│   └── app.py
├── static/
│   └── upload_cv/
└── requirements.txt

```

Now, let's create the main files for this project. We'll start with the backend.

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import engine
from . import models
from .routers import auth, folders, files

app = FastAPI()

# Create database tables
models.Base.metadata.create_all(bind=engine)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501"],  # Streamlit default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(folders.router)
app.include_router(files.router)

@app.get("/")
async def root():
    return {"message": "Welcome to the CV Screening API"}

```

Now, let's create the database connection file:

```python
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

SQLALCHEMY_DATABASE_URL = "postgresql://user:password@localhost/dbname"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

```

Next, let's define the database models:

```python
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float
from sqlalchemy.orm import relationship
from .database import Base
import datetime

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)

    folders = relationship("Folder", back_populates="owner")

class Folder(Base):
    __tablename__ = "folders"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))

    owner = relationship("User", back_populates="folders")
    files = relationship("File", back_populates="folder")

class File(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    uploaded_date = Column(DateTime, default=datetime.datetime.utcnow)
    file_type = Column(String)
    size = Column(Float)
    words = Column(Integer)
    number_page = Column(Integer)
    language = Column(String)
    status = Column(String, default="unparsed")
    folder_id = Column(Integer, ForeignKey("folders.id"))

    folder = relationship("Folder", back_populates="files")

class JobDescription(Base):
    __tablename__ = "job_descriptions"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(String)
    user_id = Column(Integer, ForeignKey("users.id"))

    owner = relationship("User")

```

Now, let's create the Pydantic schemas for request/response models:

```python
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

class UserBase(BaseModel):
    username: str

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int

    class Config:
        orm_mode = True

class FolderBase(BaseModel):
    name: str

class FolderCreate(FolderBase):
    pass

class Folder(FolderBase):
    id: int
    user_id: int

    class Config:
        orm_mode = True

class FileBase(BaseModel):
    filename: str
    file_type: str
    size: float
    words: int
    number_page: int
    language: str

class FileCreate(FileBase):
    folder_id: int

class File(FileBase):
    id: int
    uploaded_date: datetime
    status: str
    folder_id: int

    class Config:
        orm_mode = True

class JobDescriptionBase(BaseModel):
    content: str

class JobDescriptionCreate(JobDescriptionBase):
    pass

class JobDescription(JobDescriptionBase):
    id: int
    user_id: int

    class Config:
        orm_mode = True

```

Now, let's create the router files. First, the authentication router:

```python
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from .. import models, schemas
from ..database import get_db
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta

router = APIRouter()

# ... (JWT and password hashing setup)

@router.post("/token", response_model=schemas.Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/users/", response_model=schemas.User)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    hashed_password = pwd_context.hash(user.password)
    db_user = models.User(username=user.username, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

```

Now, let's create the folders router:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .. import models, schemas
from ..database import get_db
from .auth import get_current_user

router = APIRouter()

@router.post("/folders/", response_model=schemas.Folder)
def create_folder(folder: schemas.FolderCreate, db: Session = Depends(get_db), current_user: schemas.User = Depends(get_current_user)):
    db_folder = models.Folder(**folder.dict(), user_id=current_user.id)
    db.add(db_folder)
    db.commit()
    db.refresh(db_folder)
    return db_folder

@router.get("/folders/", response_model=List[schemas.Folder])
def read_folders(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user: schemas.User = Depends(get_current_user)):
    folders = db.query(models.Folder).filter(models.Folder.user_id == current_user.id).offset(skip).limit(limit).all()
    return folders

@router.get("/folders/{folder_id}", response_model=schemas.Folder)
def read_folder(folder_id: int, db: Session = Depends(get_db), current_user: schemas.User = Depends(get_current_user)):
    folder = db.query(models.Folder).filter(models.Folder.id == folder_id, models.Folder.user_id == current_user.id).first()
    if folder is None:
        raise HTTPException(status_code=404, detail="Folder not found")
    return folder

```

Finally, let's create the files router:

```python
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from .. import models, schemas
from ..database import get_db
from .auth import get_current_user
import os

router = APIRouter()

@router.post("/files/", response_model=schemas.File)
async def create_file(folder_id: int, file: UploadFile = File(...), db: Session = Depends(get_db), current_user: schemas.User = Depends(get_current_user)):
    folder = db.query(models.Folder).filter(models.Folder.id == folder_id, models.Folder.user_id == current_user.id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
  
    # Check file count limit
    file_count = db.query(models.File).filter(models.File.folder_id == folder_id).count()
    if file_count >= 100000:
        raise HTTPException(status_code=400, detail="Folder file limit reached")
  
    # Save file
    file_path = f"static/upload_cv/{current_user.id}/{folder.name}/{file.filename}"
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())
  
    # Create file record
    db_file = models.File(
        filename=file.filename,
        file_type=file.content_type,
        size=os.path.getsize(file_path) / (1024 * 1024),  # Size in MB
        words=0,  # You'll need to implement word counting
        number_page=0,  # You'll need to implement page counting
        language="",  # You'll need to implement language detection
        folder_id=folder_id
    )
    db.add(db_file)
    db.commit()
    db.refresh(db_file)
    return db_file

@router.get("/files/{folder_id}", response_model=List[schemas.File])
def read_files(folder_id: int, skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user: schemas.User = Depends(get_current_user)):
    folder = db.query(models.Folder).filter(models.Folder.id == folder_id, models.Folder.user_id == current_user.id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    files = db.query(models.File).filter(models.File.folder_id == folder_id).offset(skip).limit(limit).all()
    return files

@router.post("/parse_files/")
def parse_files(file_ids: List[int], db: Session = Depends(get_db), current_user: schemas.User = Depends(get_current_user)):
    # Implement file parsing logic here
    pass

@router.post("/job_description/", response_model=schemas.JobDescription)
def create_job_description(job_description: schemas.JobDescriptionCreate, db: Session = Depends(get_db), current_user: schemas.User = Depends(get_current_user)):
    db_jd = models.JobDescription(**job_description.dict(), user_id=current_user.id)
    db.add(db_jd)
    db.commit()
    db.refresh(db_jd)
    return db_jd

@router.post("/search_cv/")
def search_cv(job_description_id: int, db: Session = Depends(get_db), current_user: schemas.User = Depends(get_current_user)):
    # Implement CV search logic here
    pass

```

Now, let's create the Streamlit frontend:

```python
import streamlit as st
import requests
import os

API_URL = "http://localhost:8000"  # FastAPI backend URL

def login():
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        response = requests.post(f"{API_URL}/token", data={"username": username, "password": password})
        if response.status_code == 200:
            st.session_state.token = response.json()["access_token"]
            st.session_state.user_id = response.json()["user_id"]
            st.success("Logged in successfully!")
        else:
            st.error("Invalid username or password")

def list_folders():
    headers = {"Authorization": f"Bearer {st.session_state.token}"}
    response = requests.get(f"{API_URL}/folders/", headers=headers)
    if response.status_code == 200:
        folders = response.json()
        for folder in folders:
            if st.button(folder["name"]):
                st.session_state.current_folder = folder["id"]
                st.experimental_rerun()

def create_folder():
    folder_name = st.text_input("New Folder Name")
    if st.button("Create Folder"):
        headers = {"Authorization": f"Bearer {st.session_state.token}"}
        response = requests.post(f"{API_URL}/folders/", json={"name": folder_name}, headers=headers)
        if response.status_code == 200:
            st.success("Folder created successfully!")
            st.experimental_rerun()
        else:
            st.error("Faile
```
