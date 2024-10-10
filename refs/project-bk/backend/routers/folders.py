from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import os
import shutil
from pathlib import Path

import models, schemas
from database import get_db
from routers.auth import get_current_user

router = APIRouter(prefix="/folders", tags=["folders"])

UPLOAD_DIR = Path("static/upload_cv")

@router.post("/", response_model=schemas.Folder)
def create_folder(folder: schemas.FolderCreate, db: Session = Depends(get_db), current_user: schemas.User = Depends(get_current_user)):
    folder_path = UPLOAD_DIR / str(current_user.id) / folder.name
    if folder_path.exists():
        raise HTTPException(status_code=400, detail="Folder already exists")
    folder_path.mkdir(parents=True, exist_ok=True)
    
    db_folder = models.Folder(**folder.dict(), user_id=current_user.id)
    db.add(db_folder)
    db.commit()
    db.refresh(db_folder)
    return db_folder

@router.get("/", response_model=List[schemas.FolderWithDetails])
def read_folders(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user: schemas.User = Depends(get_current_user)):
    folders = db.query(models.Folder).filter(models.Folder.user_id == current_user.id).offset(skip).limit(limit).all()
    
    folder_details = []
    for folder in folders:
        folder_path = UPLOAD_DIR / str(current_user.id) / folder.name
        num_files = len(list(folder_path.glob('*')))
        size = sum(f.stat().st_size for f in folder_path.glob('**/*') if f.is_file())
        
        folder_details.append(schemas.FolderWithDetails(
            **folder.__dict__,
            num_files=num_files,
            size=size
        ))
    
    return folder_details

@router.get("/{folder_id}", response_model=schemas.FolderWithDetails)
def read_folder(folder_id: int, db: Session = Depends(get_db), current_user: schemas.User = Depends(get_current_user)):
    folder = db.query(models.Folder).filter(models.Folder.id == folder_id, models.Folder.user_id == current_user.id).first()
    if folder is None:
        raise HTTPException(status_code=404, detail="Folder not found")
    
    folder_path = UPLOAD_DIR / str(current_user.id) / folder.name
    num_files = len(list(folder_path.glob('*')))
    size = sum(f.stat().st_size for f in folder_path.glob('**/*') if f.is_file())
    
    return schemas.FolderWithDetails(
        **folder.__dict__,
        num_files=num_files,
        size=size
    )

@router.put("/{folder_id}", response_model=schemas.Folder)
def update_folder(folder_id: int, folder: schemas.FolderCreate, db: Session = Depends(get_db), current_user: schemas.User = Depends(get_current_user)):
    db_folder = db.query(models.Folder).filter(models.Folder.id == folder_id, models.Folder.user_id == current_user.id).first()
    if db_folder is None:
        raise HTTPException(status_code=404, detail="Folder not found")
    
    old_path = UPLOAD_DIR / str(current_user.id) / db_folder.name
    new_path = UPLOAD_DIR / str(current_user.id) / folder.name
    
    if old_path != new_path:
        if new_path.exists():
            raise HTTPException(status_code=400, detail="Folder with new name already exists")
        old_path.rename(new_path)
    
    db_folder.name = folder.name
    db.commit()
    db.refresh(db_folder)
    return db_folder

@router.delete("/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_folder(folder_id: int, db: Session = Depends(get_db), current_user: schemas.User = Depends(get_current_user)):
    db_folder = db.query(models.Folder).filter(models.Folder.id == folder_id, models.Folder.user_id == current_user.id).first()
    if db_folder is None:
        raise HTTPException(status_code=404, detail="Folder not found")
    
    folder_path = UPLOAD_DIR / str(current_user.id) / db_folder.name
    if folder_path.exists():
        shutil.rmtree(folder_path)
    
    # Delete all files associated with this folder
    db.query(models.File).filter(models.File.folder_id == folder_id).delete()
    
    db.delete(db_folder)
    db.commit()
    return {"ok": True}