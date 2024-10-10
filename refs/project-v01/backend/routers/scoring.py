# backend/routers/scoring.py

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
import models, schemas
from database import get_db
from routers.auth import get_current_user
import PyPDF2
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

router = APIRouter(prefix="/scoring", tags=["scoring"])

def extract_text_from_pdf(file):
    pdf_reader = PyPDF2.PdfReader(file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text()
    return text

def preprocess_text(text):
    # Implement more sophisticated text preprocessing here if needed
    return text.lower()

def calculate_similarity(cv_text, job_description):
    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform([cv_text, job_description])
    similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
    return similarity

@router.post("/{folder_id}/score")
async def score_cvs(
    folder_id: int,
    job_description: str = None,
    job_description_file: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    folder = db.query(models.Folder).filter(models.Folder.id == folder_id, models.Folder.user_id == current_user.id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    if job_description_file:
        job_description = extract_text_from_pdf(job_description_file.file)
    elif not job_description:
        raise HTTPException(status_code=400, detail="Job description is required")

    files = db.query(models.File).filter(models.File.folder_id == folder_id, models.File.status == "parsed").all()
    
    job_description = preprocess_text(job_description)
    
    scores = []
    for file in files:
        if not file.parsed_data:
            continue
        
        cv_text = preprocess_text(" ".join([
            file.parsed_data.get("name", ""),
            file.parsed_data.get("email", ""),
            " ".join(file.parsed_data.get("skills", [])),
            " ".join(file.parsed_data.get("experience", [])),
            " ".join(file.parsed_data.get("education", []))
        ]))
        
        similarity_score = calculate_similarity(cv_text, job_description)
        scores.append({
            "filename": file.filename,
            "name": file.parsed_data.get("name", "Unknown"),
            "email": file.parsed_data.get("email", "unknown@example.com"),
            "score": round(similarity_score * 100, 2)  # Convert to percentage
        })

    scores.sort(key=lambda x: x["score"], reverse=True)
    return scores