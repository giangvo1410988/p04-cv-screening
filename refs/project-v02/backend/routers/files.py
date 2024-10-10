from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from pathlib import Path
import shutil
import datetime
import magic
import PyPDF2
import os

import models, schemas
from database import get_db
from routers.auth import get_current_user

router = APIRouter(prefix="/files", tags=["files"])

UPLOAD_DIR = Path("static/upload_cv")
MAX_FILES_PER_UPLOAD = 200
MAX_FILES_PER_FOLDER = 100000
ALLOWED_EXTENSIONS = {'.pdf'}

def get_file_details(file_path: Path):
    mime = magic.Magic(mime=True)
    file_type = mime.from_file(str(file_path))
    size = file_path.stat().st_size
    words = 0
    number_page = 1
    language = "unknown"

    if file_path.suffix.lower() == '.pdf':
        with open(file_path, 'rb') as f:
            pdf_reader = PyPDF2.PdfReader(f)
            number_page = len(pdf_reader.pages)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text()
            words = len(text.split())
            language = "English"  # You might want to implement actual language detection here

    return file_type, size, words, number_page, language

@router.post("/", response_model=schemas.FileUploadResponse)
async def create_files(
    files: List[UploadFile] = File(...),
    folder_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    folder = db.query(models.Folder).filter(models.Folder.id == folder_id, models.Folder.user_id == current_user.id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    folder_path = UPLOAD_DIR / str(current_user.id) / folder.name
    if not folder_path.exists():
        raise HTTPException(status_code=404, detail="Folder not found in filesystem")

    existing_files = len(list(folder_path.glob('*')))
    if existing_files + len(files) > MAX_FILES_PER_FOLDER:
        raise HTTPException(status_code=400, detail=f"Folder would exceed the maximum limit of {MAX_FILES_PER_FOLDER} files")

    if len(files) > MAX_FILES_PER_UPLOAD:
        raise HTTPException(status_code=400, detail=f"Maximum {MAX_FILES_PER_UPLOAD} files can be uploaded at once")

    uploaded_files = []
    duplicate_files = []
    invalid_files = []
    for file in files:
        file_extension = Path(file.filename).suffix.lower()
        if file_extension not in ALLOWED_EXTENSIONS:
            invalid_files.append(file.filename)
            continue

        file_path = folder_path / file.filename
        if file_path.exists():
            duplicate_files.append(file.filename)
            continue

        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        file_type, size, words, number_page, language = get_file_details(file_path)

        db_file = models.File(
            filename=file.filename,
            file_type=file_type,
            size=size,
            words=words,
            number_page=number_page,
            language=language,
            folder_id=folder_id,
            status="unparsed",
            uploaded_date=datetime.datetime.utcnow()
        )
        db.add(db_file)
        db.commit()
        db.refresh(db_file)
        uploaded_files.append(schemas.File.from_orm(db_file))

    response = schemas.FileUploadResponse(
        uploaded_files=uploaded_files,
        message="File upload completed",
        duplicate_files=duplicate_files,
        invalid_files=invalid_files
    )

    if not uploaded_files and (duplicate_files or invalid_files):
        raise HTTPException(status_code=400, detail=response.dict())

    return response

@router.get("/", response_model=List[schemas.File])
def read_files(
    folder_id: int,
    skip: int = 0,
    limit: int = 100,
    sort_by: Optional[str] = None,
    sort_order: Optional[str] = "asc",
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    query = db.query(models.File).filter(models.File.folder_id == folder_id)
    
    folder = db.query(models.Folder).filter(models.Folder.id == folder_id, models.Folder.user_id == current_user.id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    if sort_by:
        if sort_order == "desc":
            query = query.order_by(getattr(models.File, sort_by).desc())
        else:
            query = query.order_by(getattr(models.File, sort_by))

    files = query.offset(skip).limit(limit).all()
    return files

@router.get("/{file_id}", response_model=schemas.File)
def read_file(file_id: int, db: Session = Depends(get_db), current_user: schemas.User = Depends(get_current_user)):
    file = db.query(models.File).join(models.Folder).filter(models.File.id == file_id, models.Folder.user_id == current_user.id).first()
    if file is None:
        raise HTTPException(status_code=404, detail="File not found")
    return file

@router.get("/{file_id}/download")
def download_file(file_id: int, db: Session = Depends(get_db), current_user: schemas.User = Depends(get_current_user)):
    file = db.query(models.File).join(models.Folder).filter(models.File.id == file_id, models.Folder.user_id == current_user.id).first()
    if file is None:
        raise HTTPException(status_code=404, detail="File not found")
    
    file_path = UPLOAD_DIR / str(current_user.id) / file.folder.name / file.filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found in filesystem")
    
    return FileResponse(file_path, filename=file.filename, media_type='application/pdf')

@router.put("/{file_id}", response_model=schemas.File)
def update_file(file_id: int, file: schemas.FileUpdate, db: Session = Depends(get_db), current_user: schemas.User = Depends(get_current_user)):
    db_file = db.query(models.File).join(models.Folder).filter(models.File.id == file_id, models.Folder.user_id == current_user.id).first()
    if db_file is None:
        raise HTTPException(status_code=404, detail="File not found")
    for key, value in file.dict(exclude_unset=True).items():
        setattr(db_file, key, value)
    db.commit()
    db.refresh(db_file)
    return db_file

@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_file(file_id: int, db: Session = Depends(get_db), current_user: schemas.User = Depends(get_current_user)):
    db_file = db.query(models.File).join(models.Folder).filter(models.File.id == file_id, models.Folder.user_id == current_user.id).first()
    if db_file is None:
        raise HTTPException(status_code=404, detail="File not found")
    
    file_path = UPLOAD_DIR / str(current_user.id) / db_file.folder.name / db_file.filename
    if file_path.exists():
        os.remove(file_path)
    
    db.delete(db_file)
    db.commit()
    return {"ok": True}

@router.post("/{file_id}/parse", response_model=schemas.File)
def parse_file(file_id: int, db: Session = Depends(get_db), current_user: schemas.User = Depends(get_current_user)):
    db_file = db.query(models.File).join(models.Folder).filter(models.File.id == file_id, models.Folder.user_id == current_user.id).first()
    if db_file is None:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Here you would implement the parsing logic
    # For now, we'll just update the status
    db_file.status = "parsed"
    db.commit()
    db.refresh(db_file)
    return db_file