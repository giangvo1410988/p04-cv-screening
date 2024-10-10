from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine
import models as models
from routers import auth, folders, files
from fastapi.staticfiles import StaticFiles
from routers import parsing, scoring


app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

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
app.include_router(parsing.router)
app.include_router(scoring.router)

@app.get("/")
async def root():
    return {"message": "Welcome to the CV Screening API"}