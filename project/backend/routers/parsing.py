# backend/routers/parsing.py

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
import models, schemas
from database import get_db
from routers.auth import get_current_user
import pandas as pd
from pathlib import Path
from io import BytesIO
from fastapi.responses import StreamingResponse
import PyPDF2
from routers.cvinfo import insert_cv_data
from routers import ai
import json

router = APIRouter(prefix="/parsing", tags=["parsing"])
UPLOAD_DIR = Path("static/upload_cv")


def parse_cv(file_path: Path):
    with open(file_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        cv_text = ""
        for page in pdf_reader.pages:
            cv_text += page.extract_text()
    
    prompt = ai.prompt_general_info(cv_text)
    response,_,_= ai.call_openAI(prompt, ai.api_key)
    print("==> response: ", response)

    # Handle ``` inside response: not stable case
    if "```" in response:
        response = response.split("```")[1].strip("json")

    try:
        data_dict = json.loads(response)
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
        return None

    with open("./abc.json", 'w', encoding='utf-8') as file:
        json.dump(data_dict, file, ensure_ascii=False, indent=4)
    
    return data_dict

@router.post("/{folder_id}/parse", response_model=List[schemas.File])
async def parse_folder(
    folder_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    # Find the folder
    folder = db.query(models.Folder).filter(models.Folder.id == folder_id, models.Folder.user_id == current_user.id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    # Find files in the folder
    files = db.query(models.File).filter(models.File.folder_id == folder_id).all()
    if not files:
        raise HTTPException(status_code=404, detail="No files found in the folder")

    # Create a new JobManagement entry to track parsing
    job = models.JobManagement(
        service_name="cv_parsing",
        folder_name=folder.name,
        status="parsing",
        folder_id=folder.id
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Start the parsing tasks for each file
    for file in files:
        if file.status in ["new", "parsing", "unparsed"]:
            file.status = "parsing"
            db.commit()

            file_path = UPLOAD_DIR / str(current_user.id) / folder.name / file.filename
            background_tasks.add_task(parse_and_update_file, file.id, file_path, db, job.job_id)
    
    return files


def parse_and_update_file(file_id: int, file_path: Path, db: Session, job_id: int):
    try:
        # Parse the file
        parsed_data = parse_cv(file_path)
        
        # Update the file status to "parsed" and add parsed data
        db_file = db.query(models.File).filter(models.File.id == file_id).first()
        if db_file:
            db_file.status = "parsed"
            db_file.parsed_data = parsed_data
            db.commit()

            # Insert parsed CV data into the database
            insert_cv_data(db, parsed_data, db_file.id)

    except Exception as e:
        # If an error occurs, set the file status to "failed"
        db.rollback()
        db_file = db.query(models.File).filter(models.File.id == file_id).first()
        if db_file:
            db_file.status = "failed"
            db.commit()

        # Optionally log the error
        print(f"Failed to parse file {file_id}: {e}")

    finally:
        # Check if all files in the folder have completed parsing
        job = db.query(models.JobManagement).filter(models.JobManagement.job_id == job_id).first()
        if job:
            folder_files = db.query(models.File).filter(models.File.folder_id == job.folder_id).all()

            if all(file.status == "parsed" for file in folder_files):
                job.status = "parsed_complete"
            elif any(file.status == "failed" for file in folder_files):
                job.status = "parsed_apart"
            else:
                job.status = "parsing"  # This means that some files are still being processed

            db.commit()

@router.get("/{folder_id}/status", response_model=List[schemas.File])
async def get_parsing_status(
    folder_id: int,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    folder = db.query(models.Folder).filter(models.Folder.id == folder_id, models.Folder.user_id == current_user.id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    files = db.query(models.File).filter(models.File.folder_id == folder_id).all()
    return [schemas.File.from_orm(file) for file in files]

@router.get("/{folder_id}/download")
async def download_parsed_data(
    folder_id: int,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    folder = db.query(models.Folder).filter(models.Folder.id == folder_id, models.Folder.user_id == current_user.id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    files = db.query(models.File).filter(models.File.folder_id == folder_id, models.File.status == "parsed").all()
    
    parsed_data = []
    for file in files:
        file_data = {
            "filename": file.filename,
            "name": file.parsed_data.get("name", ""),
            "email": file.parsed_data.get("email", ""),
            "skills": ", ".join(file.parsed_data.get("skills", [])),
            "experience": "\n".join(file.parsed_data.get("experience", [])),
            "education": "\n".join(file.parsed_data.get("education", []))
        }
        parsed_data.append(file_data)

    df = pd.DataFrame(parsed_data)
    excel_file = BytesIO()
    df.to_excel(excel_file, index=False)
    excel_file.seek(0)

    return StreamingResponse(
        excel_file,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=parsed_data_{folder.name}.xlsx"}
    )
