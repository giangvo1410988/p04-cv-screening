# backend/routers/search.py

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
import models
import schemas
from database import get_db
from routers.auth import get_current_user
from sqlalchemy import func
import json
from pathlib import Path
import PyPDF2
from routers import ai
from sqlalchemy import or_


router = APIRouter(prefix="/search", tags=["search"])
UPLOAD_DIR = Path("static/upload_job_descriptions")

@router.post("/candidates")
async def search_candidates(
    job_title: Optional[List[str]] = None,
    current_job: Optional[List[str]] = None,
    industry: Optional[List[str]] = None,
    city: Optional[str] = None,
    country: Optional[str] = None,
    old_range: Optional[List[int]] = None,  # A >= x >= B
    language: Optional[List[str]] = None,
    skill: Optional[List[str]] = None,
    degree: Optional[str] = None,
    major: Optional[str] = None,
    level: Optional[List[str]] = None,
    point_range: Optional[List[int]] = None,  # A >= x >= B
    yoe_range: Optional[List[int]] = None,  # A >= x >= B
    status: Optional[str] = "AI-Checked",
    folder_names: Optional[List[str]] = None,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    # Find the folders based on user and folder names (case-insensitive)
    if folder_names:
        folders = db.query(models.Folder).filter(
            models.Folder.user_id == current_user.id,
            func.lower(models.Folder.name).in_(map(str.lower, folder_names))
        ).all()
    else:
        folders = db.query(models.Folder).filter(
            models.Folder.user_id == current_user.id
        ).all()

    if not folders:
        raise HTTPException(status_code=404, detail="No matching folders found")

    # Get file IDs from the folders
    file_ids = [file.id for folder in folders for file in folder.files]

    # Query CVInfo based on file IDs
    query = db.query(models.CVInfo).filter(models.CVInfo.file_id.in_(file_ids))

    # Apply less strict filters to the query
    if job_title:
        job_title_filters = [models.CVInfo.job_title.ilike(f"%{jt}%") for jt in job_title]
        query = query.filter(or_(*job_title_filters))
    
    if current_job:
        current_job_filters = [func.lower(models.Experience.job_title).ilike(f"%{cj.lower()}%") for cj in current_job]
        query = query.join(models.Experience).filter(or_(*current_job_filters))

    if industry:
        industry_filters = [models.CVInfo.industry.ilike(f"%{ind}%") for ind in industry]
        query = query.filter(or_(*industry_filters))

    if city:
        query = query.filter(models.CVInfo.city_province.ilike(f"%{city}%"))

    if country:
        query = query.filter(models.CVInfo.country.ilike(f"%{country}%"))

    if old_range and len(old_range) == 2:
        query = query.filter(models.CVInfo.date_of_birth.between(old_range[1], old_range[0]))

    if language:
        language_filters = [func.lower(models.Certificate.language).ilike(f"%{lang.lower()}%") for lang in language]
        query = query.join(models.Certificate).filter(or_(*language_filters))

    if skill:
        # Use ilike for partial match on skills
        skill_filters = [func.array_to_string(models.CVInfo.skills, ' ').ilike(f"%{s.lower()}%") for s in skill]
        query = query.filter(or_(*skill_filters))

    if degree:
        query = query.join(models.Education).filter(models.Education.degree.ilike(f"%{degree}%"))

    if major:
        query = query.join(models.Education).filter(models.Education.major.ilike(f"%{major}%"))

    if level:
        level_filters = [models.CVInfo.level.ilike(f"%{lvl}%") for lvl in level]
        query = query.filter(or_(*level_filters))

    if point_range and len(point_range) == 2:
        query = query.join(models.User).filter(models.User.point.between(point_range[1], point_range[0]))

    if yoe_range and len(yoe_range) == 2:
        query = query.filter(models.CVInfo.yoe.between(yoe_range[1], yoe_range[0]))

    # Execute query and return results
    candidates = query.all()
    return [schemas.CVInfoResponse.from_orm(candidate) for candidate in candidates]



def parse_job_description(file_path: Path):
    with open(file_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        job_description_text = ""
        for page in pdf_reader.pages:
            job_description_text += page.extract_text()
    
    prompt = ai.prompt_job_description(job_description_text)
    response, _, _ = ai.call_openAI(prompt, ai.api_key)

    # Handle ``` inside response: not stable case
    if "```" in response:
        response = response.split("```")[1].strip("json")

    try:
        data_dict = json.loads(response)
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
        return None

    return data_dict

@router.post("/parse")
async def upload_and_parse_job_description(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    # Save the uploaded file
    if not UPLOAD_DIR.exists():
        UPLOAD_DIR.mkdir(parents=True)

    file_path = UPLOAD_DIR / file.filename

    with open(file_path, "wb") as buffer:
        buffer.write(file.file.read())

    # Parse the job description PDF
    job_description_data = parse_job_description(file_path)

    if not job_description_data:
        raise HTTPException(status_code=500, detail="Failed to extract information from the job description PDF.")

    # Return the extracted job information
    return job_description_data


@router.post("/search_from_job_description")
async def search_from_job_description(
    job_description: schemas.JobDescription,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    # Use the extracted job description data to search for candidates
    job_info = job_description.job_information

    job_title = [job_info.job_title] if job_info.job_title else None
    industry = [job_info.industry] if job_info.industry else None
    city = job_info.location.city if job_info.location and job_info.location.city else None
    country = job_info.location.country if job_info.location and job_info.location.country else None
    skill = job_info.job_requirements.skills if job_info.job_requirements and job_info.job_requirements.skills else None
    degree = job_info.job_requirements.education.degree if job_info.job_requirements and job_info.job_requirements.education and job_info.job_requirements.education.degree else None
    major = job_info.job_requirements.education.major if job_info.job_requirements and job_info.job_requirements.education and job_info.job_requirements.education.major else None

    print(
        job_title,
        industry,
        city,
        country,
        skill,
        degree,
        major
    )
    candidates = await search_candidates(
        job_title=job_title,
        industry=industry,
        city=city,
        country=country,
        skill=skill,
        degree=degree,
        major=major,
        db=db,
        current_user=current_user
    )

    return candidates
