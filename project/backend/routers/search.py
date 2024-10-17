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
import typesense
import re 

router = APIRouter(prefix="/search", tags=["search"])
UPLOAD_DIR = Path("static/upload_job_descriptions")


### SQLAlchemy Search Implementation (For Non-Typesense Related Search) ###
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
    SIMILARITY_THRESHOLD = 0.3  # Adjust this threshold based on how strict the matching should be
    
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

    # Start building the query with CVInfo table
    query = db.query(models.CVInfo, models.File.filename).join(models.File, models.CVInfo.file_id == models.File.id).filter(models.CVInfo.file_id.in_(file_ids))

    # Collect all conditions to apply as 'OR' for relaxed matching
    or_conditions = []

    # Apply fuzzy matching filters for job title using trigram similarity
    if job_title:
        job_title_filters = [
            func.similarity(models.CVInfo.job_title, jt) >= SIMILARITY_THRESHOLD for jt in job_title
        ]
        or_conditions.append(or_(*job_title_filters))

    # Fuzzy matching for current job titles from experience
    if current_job:
        query = query.join(models.Experience)
        current_job_filters = [
            func.similarity(func.lower(models.Experience.job_title), cj.lower()) >= SIMILARITY_THRESHOLD for cj in current_job
        ]
        or_conditions.append(or_(*current_job_filters))

    # Fuzzy matching for industry
    if industry:
        industry_filters = [
            func.similarity(models.CVInfo.industry, ind) >= SIMILARITY_THRESHOLD for ind in industry
        ]
        or_conditions.append(or_(*industry_filters))

    # Fuzzy matching for city
    if city:
        or_conditions.append(func.similarity(models.CVInfo.city_province, city) >= SIMILARITY_THRESHOLD)

    # Fuzzy matching for country
    if country:
        or_conditions.append(func.similarity(models.CVInfo.country, country) >= SIMILARITY_THRESHOLD)

    # Date range filtering for old_range (age)
    if old_range and len(old_range) == 2:
        or_conditions.append(models.CVInfo.date_of_birth.between(old_range[1], old_range[0]))

    # Fuzzy matching for languages
    if language:
        query = query.join(models.Certificate)
        language_filters = [
            func.similarity(func.lower(models.Certificate.language), lang.lower()) >= SIMILARITY_THRESHOLD for lang in language
        ]
        or_conditions.append(or_(*language_filters))

    # Fuzzy matching for skills - prioritize skill matching
    if skill:
        skill_filters = [
            func.array_to_string(models.CVInfo.skills, ' ').ilike(f"%{s.lower()}%") for s in skill
        ]
        or_conditions.append(or_(*skill_filters))

    # Conditionally join cv_education only once and filter for degree and major
    if degree or major:
        query = query.join(models.Education)  # Only join once
        if degree:
            or_conditions.append(models.Education.degree.ilike(f"%{degree}%"))
        if major:
            or_conditions.append(models.Education.major.ilike(f"%{major}%"))

    # Fuzzy matching for level
    if level:
        level_filters = [
            func.similarity(models.CVInfo.level, lvl) >= SIMILARITY_THRESHOLD for lvl in level
        ]
        or_conditions.append(or_(*level_filters))

    # Point range filtering
    if point_range and len(point_range) == 2:
        or_conditions.append(models.User.point.between(point_range[1], point_range[0]))

    # Years of experience range filtering
    if yoe_range and len(yoe_range) == 2:
        or_conditions.append(models.CVInfo.yoe.between(yoe_range[1], yoe_range[0]))

    # Apply 'OR' conditions for relaxed matching - keeps candidates if at least one field matches
    if or_conditions:
        query = query.filter(or_(*or_conditions))

    # Execute query and return results
    candidates = query.all()

    # Include file path in the response
    return [
        schemas.CVInfoResponse.from_orm(candidate[0]).dict() | {"File Name": str(candidate[1])}
        for candidate in candidates
    ]


### PDF Parsing and Job Description Parsing ###
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


### Typesense-Related Search and Indexing Logic ###


# Initialize Typesense client
def get_typesense_client():
    client = typesense.Client({
        'nodes': [{
            'host': 'localhost',  # Update with your Typesense server details
            'port': '8108',
            'protocol': 'http',
        }],
        'api_key': 'typesensemulti',  # Use your Typesense API key
        'connection_timeout_seconds': 2
    })
    return client


# Batch indexing all candidates
async def batch_index_candidates(db: Session, user_id: int):
    client = get_typesense_client()

    # Print out the collections in Typesense
    try:
        collections = client.collections.retrieve()
        print("Available Collections in Typesense:")
        for collection in collections:
            print(f"- {collection['name']}")
    except Exception as e:
        print(f"Error retrieving collections: {e}")
        return {"status": "Error retrieving collections"}

    # Get folders belonging to the user
    folders = db.query(models.Folder).filter(models.Folder.user_id == user_id).all()

    # Get file IDs from the folders
    file_ids = [file.id for folder in folders for file in folder.files]

    # Start building the query with CVInfo table, filtered by file IDs
    query = db.query(models.CVInfo, models.File.filename).join(models.File, models.CVInfo.file_id == models.File.id).filter(models.CVInfo.file_id.in_(file_ids))

    # Join additional tables for more comprehensive candidate data
    query = query.outerjoin(models.Experience).outerjoin(models.Certificate).outerjoin(models.Education)

    # Execute the query to get all candidate data
    candidates = query.all()

    # Iterate through candidates and index them
    for candidate, filename in candidates:
        document = {
            'id': str(candidate.id),
            'job_title': candidate.job_title,
            'industry': candidate.industry,
            'city': candidate.city_province,
            'country': candidate.country,
            'skills': candidate.skills,
            'degree': candidate.education[0].degree if candidate.education else None,
            'major': candidate.education[0].major if candidate.education else None,
            'file_name': filename
        }
        try:
            client.collections['candidates'].documents.upsert(document)
        except Exception as e:
            print(f"Error indexing candidate {candidate.id}: {e}")

    return {"status": "Indexing completed"}



# Real-time indexing a single candidate
async def index_candidate(candidate_data):
    client = get_typesense_client()

    document = {
        'id': str(candidate_data.id),
        'job_title': candidate_data.job_title,
        'industry': candidate_data.industry,
        'city': candidate_data.city,
        'country': candidate_data.country,
        'skills': candidate_data.skills,
        'degree': candidate_data.degree,
        'major': candidate_data.major
    }
    try:
        client.collections['candidates'].documents.upsert(document)
    except Exception as e:
        print(f"Error indexing candidate {candidate_data.id}: {e}")

async def search_candidates_typesense(
    job_title: Optional[List[str]] = None,
    industry: Optional[List[str]] = None,
    city: Optional[str] = None,
    country: Optional[str] = None,
    skill: Optional[List[str]] = None,
    degree: Optional[str] = None,
    major: Optional[List[str]] = None,
    current_user: schemas.User = Depends(get_current_user)
):
    client = get_typesense_client()

    search_params = {
        'q': "*",  # Use '*' to match all documents, then filter
        'query_by': 'job_title,industry,city,country,skills,degree,major',
        'num_typos': 2,  # Allow up to 2 typos for fuzzy matching
        'drop_tokens_threshold': 1,  # Allow some tokens to be dropped if no match is found
        'query_by_weights': '4,3,2,1,5,3,2',  # Give more weight to some fields (e.g., job_title and skills)
        'page': 1,
        'per_page': 10
    }

    filters = []

    # Add filters for job title (fuzzy matching allowed using :=)
    if job_title:
        filters.append("(" + " || ".join([f"job_title:={jt}" for jt in job_title]) + ")")

    # Add filters for industry (fuzzy matching allowed using :=)
    if industry:
        filters.append("(" + " || ".join([f"industry:={ind}" for ind in industry]) + ")")

    # Add filter for city (exact match using ==)
    if city:
        filters.append(f"city:={city}")

    # Add filter for country (exact match using ==)
    if country:
        filters.append(f"country:={country}")

    # Add filter for skills (fuzzy matching allowed using :=)
    if skill:
        filters.append("(" + " || ".join([f"skills:={s}" for s in skill]) + ")")

    # Add filter for degree (exact match using ==)
    if degree:
        filters.append(f"degree:={degree}")

    # Add filter for major (fuzzy matching allowed using :=)
    if major:
        filters.append("(" + " || ".join([f"major:={m}" for m in major]) + ")")

    # Combine all filters using '||' (OR logic) for more forgiving search
    if filters:
        search_params['filter_by'] = " || ".join(filters)  # Use OR logic here instead of AND

    # Debug: Print the final search parameters
    print("Search Parameters:", search_params)

    # Execute the search
    search_result = client.collections['candidates'].documents.search(search_params)

    # Process the search results
    candidates = [
        {
            "id": result['document']['id'],
            "job_title": result['document']['job_title'],
            "industry": result['document']['industry'],
            "city": result['document']['city'],
            "country": result['document']['country'],
            "skills": result['document']['skills'],
            "degree": result['document']['degree'],
            "major": result['document']['major'],
        }
        for result in search_result['hits']
    ]

    return candidates



def escape_special_characters(value: str) -> str:
    # Escape special characters for Typesense, like parentheses and apostrophes
    escaped_value = re.sub(r"([\\'()])", r"\\\1", value)
    # Escape commas if they appear in any value, they might need special handling
    escaped_value = escaped_value.replace(",", r"\,")
    return escaped_value

@router.post("/search_from_job_description")
async def search_from_job_description(
    job_description: schemas.JobDescription,
    current_user: schemas.User = Depends(get_current_user)
):
    # Job Title
    job_title = None
    if job_description.job_title:
        job_title = [escape_special_characters(jt.strip()) for jt in job_description.job_title.split(',')]

    # Industry
    industry = None
    if job_description.industry:
        industry = [escape_special_characters(ind.strip()) for ind in job_description.industry.split(',')]

    # City
    city = None
    if job_description.location and job_description.location.city:
        city = escape_special_characters(job_description.location.city.strip())

    # Country
    country = None
    if job_description.location and job_description.location.country:
        country = escape_special_characters(job_description.location.country.strip())

    # Skills
    skill = None
    if job_description.job_requirements and job_description.job_requirements.skills:
        skill = [escape_special_characters(s.strip()) for s in job_description.job_requirements.skills]

    # Degree
    degree = None
    if (job_description.job_requirements and
        job_description.job_requirements.education and
        job_description.job_requirements.education.degree):
        degree = escape_special_characters(job_description.job_requirements.education.degree.strip())

    # Major
    major = None
    if (job_description.job_requirements and
        job_description.job_requirements.education and
        job_description.job_requirements.education.major):
        major = [escape_special_characters(m.strip()) for m in job_description.job_requirements.education.major.split(',')]

    # Debugging: print the fields being passed
    print("Job Title:", job_title)
    print("Industry:", industry)
    print("City:", city)
    print("Country:", country)
    print("Skills:", skill)
    print("Degree:", degree)
    print("Major:", major)

    candidates = await search_candidates_typesense(
        job_title=job_title,
        industry=industry,
        city=city,
        country=country,
        skill=skill,
        degree=degree,
        major=major,
        current_user=current_user
    )

    return candidates



### Endpoint to Batch Index All Candidates ###
@router.post("/index_all_candidates")
async def index_all_candidates(current_user: schemas.User = Depends(get_current_user),db: Session = Depends(get_db)):
    status = await batch_index_candidates(db,user_id=current_user.id)
    return status


### Index Candidate When Created ###
@router.post("/create_candidate")
async def create_candidate(candidate_data: schemas.CandidateCreate, db: Session = Depends(get_db)):
    new_candidate = models.Candidate(
        job_title=candidate_data.job_title,
        industry=candidate_data.industry,
        city=candidate_data.city,
        country=candidate_data.country,
        skills=candidate_data.skills,
        degree=candidate_data.degree,
        major=candidate_data.major
    )

    db.add(new_candidate)
    db.commit()
    db.refresh(new_candidate)

    await index_candidate(new_candidate)

    return {"message": "Candidate created and indexed", "candidate_id": new_candidate.id}

@router.get("/fetch_cv_info")
async def fetch_cv_info(
    folder_names: Optional[List[str]] = None,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    # Find folders based on user and folder names (case-insensitive)
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
    cv_infos = db.query(models.CVInfo).filter(models.CVInfo.file_id.in_(file_ids)).all()

    # Extract relevant information for populating dropdowns and filters in the search UI
    job_titles = list(set([cv.job_title for cv in cv_infos if cv.job_title]))
    industries = list(set([cv.industry for cv in cv_infos if cv.industry]))
    cities = list(set([cv.city_province for cv in cv_infos if cv.city_province]))
    countries = list(set([cv.country for cv in cv_infos if cv.country]))
    skills = list(set([skill for cv in cv_infos for skill in (cv.skills or [])]))
    degrees = list(set([edu.degree for cv in cv_infos for edu in cv.education if edu.degree]))
    majors = list(set([edu.major for cv in cv_infos for edu in cv.education if edu.major]))

    return {
        "job_titles": job_titles,
        "industries": industries,
        "cities": cities,
        "countries": countries,
        "skills": skills,
        "degrees": degrees,
        "majors": majors,
    }