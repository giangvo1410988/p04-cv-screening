from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
import models
import schemas
from database import get_db
from routers.auth import get_current_user
import json
from pathlib import Path
import PyPDF2
from routers import ai
from sqlalchemy import cast, Float, or_, func, and_
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
    point_range: Optional[List[float]] = None,  # A >= x >= B
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

    # Strict GPA filtering based on point_range
    if point_range and len(point_range) == 2:
        query = query.join(models.Education)
        # Strictly exclude None and empty string values and filter GPA within range
        or_conditions.append(
            and_(
                models.Education.gpa.isnot(None),  # Ensure GPA is not None
                models.Education.gpa != "",  # Exclude empty string values
                cast(models.Education.gpa, Float).between(point_range[0], point_range[1])  # Ensure GPA is within range
            )
        )

    # Strict Years of Experience (yoe) filtering based on yoe_range
    if yoe_range and len(yoe_range) == 2:
        or_conditions.append(
            and_(
                models.CVInfo.yoe.isnot(None),  # Ensure yoe is not None
                models.CVInfo.yoe.between(yoe_range[0], yoe_range[1])  # Ensure yoe is within range
            )
        )

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

    # Ensure the 'candidates' collection exists
    try:
        client.collections['candidates'].retrieve()
    except Exception:
        # Define the schema for the 'candidates' collection
        schema = {
            'name': 'candidates',
            'fields': [
                {'name': 'id', 'type': 'string'},
                {'name': 'job_title', 'type': 'string', 'facet': True},
                {'name': 'industry', 'type': 'string', 'facet': True},
                {'name': 'city', 'type': 'string', 'facet': True},
                {'name': 'country', 'type': 'string', 'facet': True},
                {'name': 'skills', 'type': 'string[]', 'facet': True},
                {'name': 'degree', 'type': 'string', 'facet': True},
                {'name': 'major', 'type': 'string', 'facet': True},
                {'name': 'level', 'type': 'string[]', 'facet': True},  # Multiple levels can be stored as array
                {'name': 'language', 'type': 'string[]', 'facet': True},
                {'name': 'points', 'type': 'float', 'facet': True},
                {'name': 'yoe', 'type': 'int32', 'facet': True},
                {'name': 'file_name', 'type': 'string'},
            ],
            'default_sorting_field': 'points',
        }
        client.collections.create(schema)

    # Get folders belonging to the user
    folders = db.query(models.Folder).filter(models.Folder.user_id == user_id).all()

    if not folders:
        print("No folders found for the user.")
        return {"status": "No folders found for the user."}

    # Get file IDs from the folders
    file_ids = [file.id for folder in folders for file in folder.files]

    # Start building the query with CVInfo table, filtered by file IDs
    query = (
        db.query(
            models.CVInfo,
            models.File.filename,
            models.Experience.job_title.label('current_job_title'),
            models.Certificate.language.label('certificate_language'),
            models.Education.degree.label('degree'),
            models.Education.major.label('major'),
            models.Education.gpa.label('gpa'),
            models.Experience.level.label('experience_level')
        )
        .join(models.File, models.CVInfo.file_id == models.File.id)
        .filter(models.CVInfo.file_id.in_(file_ids))
        .outerjoin(models.Experience)
        .outerjoin(models.Certificate)
        .outerjoin(models.Education)
    )

    # Execute the query to get all candidate data
    candidates = query.all()

    # Prepare documents for Typesense
    documents = []
    for candidate_data in candidates:
        cv_info = candidate_data[0]
        filename = candidate_data[1]
        certificate_language = candidate_data[3]
        degree = candidate_data[4]
        major = candidate_data[5]
        gpa = candidate_data[6]

        # Collect multiple levels from experiences
        experience_levels = [
            experience.level for experience in cv_info.experience if experience.level
        ] or [candidate_data[7]]  # If no levels found, take level from query

        document = {
            'id': str(cv_info.id),
            'job_title': cv_info.job_title or '',
            'industry': cv_info.industry or '',
            'city': cv_info.city_province or '',
            'country': cv_info.country or '',
            'skills': cv_info.skills or [],
            'degree': degree or '',
            'major': major or '',
            'level': experience_levels,  # Multiple levels as an array
            'language': [certificate_language] if certificate_language else [],
            'points': float(gpa) if gpa else 0.0,
            'yoe': cv_info.yoe if cv_info.yoe is not None else 0,
            'file_name': filename or '',
        }
        documents.append(document)

    # Batch import documents into Typesense
    try:
        client.collections['candidates'].documents.import_(documents, {'action': 'upsert'})
    except Exception as e:
        print(f"Error indexing candidates: {e}")

    return {"status": "Indexing completed"}




# Real-time indexing a single candidate
async def index_candidate(candidate_data):
    client = get_typesense_client()

    document = {
        'id': str(candidate_data.id),
        'job_title': candidate_data.job_title,
        'current_job': candidate_data.current_job,  # Handle current_job field
        'industry': candidate_data.industry,
        'city': candidate_data.city,
        'country': candidate_data.country,
        'skills': candidate_data.skills,
        'degree': candidate_data.degree,
        'major': candidate_data.major,
        'age': candidate_data.age,  # Add age field if available
        'points': candidate_data.points  # Add points field if available
    }
    try:
        client.collections['candidates'].documents.upsert(document)
    except Exception as e:
        print(f"Error indexing candidate {candidate_data.id}: {e}")

async def search_candidates_typesense(
    job_title: Optional[List[str]] = None,
    current_job: Optional[List[str]] = None,
    industry: Optional[List[str]] = None,
    city: Optional[str] = None,
    country: Optional[str] = None,
    old_range: Optional[List[int]] = None,  # A >= x >= B (age range)
    language: Optional[List[str]] = None,
    skill: Optional[List[str]] = None,
    degree: Optional[str] = None,
    major: Optional[str] = None,
    level: Optional[List[str]] = None,
    point_range: Optional[List[float]] = None,  # A >= x >= B (points range)
    yoe_range: Optional[List[int]] = None,  # A >= x >= B (years of experience)
    folder_names: Optional[List[str]] = None,
    current_user: schemas.User = Depends(get_current_user)
):
    client = get_typesense_client()

    search_params = {
        'q': "*",  # Use '*' to match all documents, then filter
        'query_by': 'job_title,industry,city,country,skills,degree,major,level,language',
        'num_typos': 2,
        'drop_tokens_threshold': 1,
        'query_by_weights': '4,2,2,2,3,2,2,2,2',
        'page': 1,
        'per_page': 100  # Adjust per_page as needed
    }

    filters = []

    # Job Title
    if job_title:
        filters.append("(" + " || ".join([f"job_title:='{escape_special_characters(jt)}'" for jt in job_title]) + ")")

    # Current Job
    if current_job:
        filters.append("(" + " || ".join([f"current_job:='{escape_special_characters(cj)}'" for cj in current_job]) + ")")

    # Industry
    if industry:
        filters.append("(" + " || ".join([f"industry:='{escape_special_characters(ind)}'" for ind in industry]) + ")")

    # City
    if city:
        filters.append(f"city:='{escape_special_characters(city)}'")

    # Country
    if country:
        filters.append(f"country:='{escape_special_characters(country)}'")

    # Age Range
    if old_range and len(old_range) == 2:
        min_age, max_age = min(old_range), max(old_range)
        filters.append(f"age >= {min_age} && age <= {max_age}")

    # Language
    if language:
        filters.append("(" + " || ".join([f"language:='{escape_special_characters(lang)}'" for lang in language]) + ")")

    # Skills
    if skill:
        filters.append("(" + " && ".join([f"skills:='{escape_special_characters(s)}'" for s in skill]) + ")")

    # Degree
    if degree:
        filters.append(f"degree:='{escape_special_characters(degree)}'")

    # Major
    if major:
        filters.append(f"major:='{escape_special_characters(major)}'")

    # Level
    if level:
        filters.append("(" + " || ".join([f"level:='{escape_special_characters(lvl)}'" for lvl in level]) + ")")

    # Points Range
    if point_range and len(point_range) == 2:
        min_points, max_points = min(point_range), max(point_range)
        filters.append(f"points >= {min_points} && points <= {max_points}")

    # Years of Experience Range
    if yoe_range and len(yoe_range) == 2:
        min_yoe, max_yoe = min(yoe_range), max(yoe_range)
        filters.append(f"yoe >= {min_yoe} && yoe <= {max_yoe}")

    # Folder Names (if needed)
    if folder_names:
        filters.append("(" + " || ".join([f"folder_names:='{escape_special_characters(fn)}'" for fn in folder_names]) + ")")

    # Combine all filters using '&&' (AND logic)
    if filters:
        search_params['filter_by'] = " && ".join(filters)

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
            "level": result['document']['level'],  # Corrected level handling
            "language": result['document']['language'],
            "points": result['document'].get('points'),
            "yoe": result['document'].get('yoe'),
            "file_name": result['document'].get('file_name')
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
    if job_description.job_requirements and job_description.job_requirements.education and job_description.job_requirements.education.degree:
        degree = escape_special_characters(job_description.job_requirements.education.degree.strip())

    # Major
    major = None
    if job_description.job_requirements and job_description.job_requirements.education and job_description.job_requirements.education.major:
        major = escape_special_characters(job_description.job_requirements.education.major.strip())

    # Level (update to correctly access from job_description directly)
    level = None
    if job_description.level:
        level = [escape_special_characters(job_description.level.strip())]

    # Language
    language = None
    if job_description.job_requirements and job_description.job_requirements.languages:
        language = [escape_special_characters(lang.strip()) for lang in job_description.job_requirements.languages]

    # Points range (min and max) - Fixed access to points attributes
    point_range = None
    if job_description.job_requirements and job_description.job_requirements.points:
        min_points = job_description.job_requirements.points.min_points
        max_points = job_description.job_requirements.points.max_points
        if min_points is not None and max_points is not None:
            point_range = [min_points, max_points]

    # Years of Experience range
    yoe_range = None
    if job_description.job_requirements and job_description.job_requirements.experience:
        min_yoe = job_description.job_requirements.experience.yoe
        max_yoe = job_description.job_requirements.experience.yoe
        if min_yoe is not None and max_yoe is not None:
            yoe_range = [min_yoe, max_yoe]

    # Debugging: print the fields being passed
    print("Job Title:", job_title)
    print("Industry:", industry)
    print("City:", city)
    print("Country:", country)
    print("Skills:", skill)
    print("Degree:", degree)
    print("Major:", major)
    print("Level:", level)
    print("Language:", language)
    print("Points Range:", point_range)
    print("Years of Experience Range:", yoe_range)

    candidates = await search_candidates_typesense(
        job_title=job_title,
        industry=industry,
        city=city,
        country=country,
        language=language,
        skill=skill,
        degree=degree,
        major=major,
        level=level,  # Correctly passed level here
        point_range=point_range,
        yoe_range=yoe_range,
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

