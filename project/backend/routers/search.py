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
from sqlalchemy import cast, Float, or_, func, and_, desc, literal
import typesense
import re 

router = APIRouter(prefix="/search", tags=["search"])
UPLOAD_DIR = Path("static/upload_job_descriptions")


from sqlalchemy import func, or_, and_, desc, cast, Float, literal
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException
from typing import List, Optional
from datetime import datetime

@router.post("/candidates")
async def search_candidates(
    job_title: Optional[List[str]] = None,
    current_job: Optional[List[str]] = None,
    industry: Optional[List[str]] = None,
    city: Optional[str] = None,
    country: Optional[str] = None,
    old_range: Optional[List[int]] = None,
    language: Optional[List[str]] = None,
    skill: Optional[List[str]] = None,
    degree: Optional[str] = None,
    major: Optional[str] = None,
    level: Optional[List[str]] = None,
    point_range: Optional[List[float]] = None,
    yoe_range: Optional[List[int]] = None,
    status: Optional[str] = "AI-Checked",
    folder_names: Optional[List[str]] = None,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    SIMILARITY_THRESHOLD = 0.3
    
    # Define weights for different criteria
    WEIGHTS = {
        'job_title': 0.25,
        'skill': 0.20,
        'industry': 0.15,
        'level': 0.10,
        'degree': 0.10,
        'major': 0.08,
        'language': 0.05,
        'city': 0.04,
        'country': 0.03
    }

    # Find the folders
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

    # Start building base query
    base_query = db.query(
        models.CVInfo,
        models.File.filename
    ).join(
        models.File,
        models.CVInfo.file_id == models.File.id
    ).filter(
        models.CVInfo.file_id.in_(file_ids)
    )

    # Initialize lists for similarity calculations and conditions
    similarity_conditions = []
    or_conditions = []
    and_conditions = []

    # Build similarity expressions and conditions for job title
    if job_title:
        job_sim = func.greatest(*[
            func.similarity(models.CVInfo.job_title, jt)
            for jt in job_title
        ]).label('job_title_similarity')
        similarity_conditions.append((job_sim, WEIGHTS['job_title']))
        or_conditions.extend([
            func.similarity(models.CVInfo.job_title, jt) >= SIMILARITY_THRESHOLD
            for jt in job_title
        ])

    # Handle current job search
    if current_job:
        base_query = base_query.join(models.Experience)
        current_job_filters = [
            func.similarity(func.lower(models.Experience.job_title), cj.lower()) >= SIMILARITY_THRESHOLD
            for cj in current_job
        ]
        or_conditions.extend(current_job_filters)

    # Handle industry similarity
    if industry:
        industry_sim = func.greatest(*[
            func.similarity(models.CVInfo.industry, ind)
            for ind in industry
        ]).label('industry_similarity')
        similarity_conditions.append((industry_sim, WEIGHTS['industry']))
        or_conditions.extend([
            func.similarity(models.CVInfo.industry, ind) >= SIMILARITY_THRESHOLD
            for ind in industry
        ])

    # Handle city similarity
    if city:
        city_sim = func.similarity(
            models.CVInfo.city_province, city
        ).label('city_similarity')
        similarity_conditions.append((city_sim, WEIGHTS['city']))
        or_conditions.append(
            func.similarity(models.CVInfo.city_province, city) >= SIMILARITY_THRESHOLD
        )

    # Handle country similarity
    if country:
        country_sim = func.similarity(
            models.CVInfo.country, country
        ).label('country_similarity')
        similarity_conditions.append((country_sim, WEIGHTS['country']))
        or_conditions.append(
            func.similarity(models.CVInfo.country, country) >= SIMILARITY_THRESHOLD
        )

    # Handle age range
    if old_range and len(old_range) == 2:
        current_year = datetime.now().year
        min_year = current_year - old_range[1]
        max_year = current_year - old_range[0]
        and_conditions.append(
            models.CVInfo.date_of_birth.between(
                f"{min_year}-01-01",
                f"{max_year}-12-31"
            )
        )

    # Handle language search
    if language:
        base_query = base_query.join(models.Certificate)
        language_sim = func.greatest(*[
            func.similarity(func.lower(models.Certificate.language), lang.lower())
            for lang in language
        ]).label('language_similarity')
        similarity_conditions.append((language_sim, WEIGHTS['language']))
        or_conditions.extend([
            func.similarity(func.lower(models.Certificate.language), lang.lower()) >= SIMILARITY_THRESHOLD
            for lang in language
        ])

    # Handle skills search
    if skill and len(skill) > 0:
        skill_matches = [
            func.array_to_string(models.CVInfo.skills, ' ').ilike(f'%{s.lower()}%')
            for s in skill
        ]
        skill_sim = (
            func.sum(cast(expr, Float) for expr in skill_matches) / len(skill)
        ).label('skill_similarity')
        similarity_conditions.append((skill_sim, WEIGHTS['skill']))
        or_conditions.extend(skill_matches)

    # Handle education (degree and major)
    if degree or major:
        base_query = base_query.join(models.Education)
        if degree:
            degree_sim = func.similarity(
                models.Education.degree, degree
            ).label('degree_similarity')
            similarity_conditions.append((degree_sim, WEIGHTS['degree']))
            or_conditions.append(models.Education.degree.ilike(f"%{degree}%"))
        
        if major:
            major_sim = func.similarity(
                models.Education.major, major
            ).label('major_similarity')
            similarity_conditions.append((major_sim, WEIGHTS['major']))
            or_conditions.append(models.Education.major.ilike(f"%{major}%"))

    # Handle level similarity
    if level:
        level_sim = func.greatest(*[
            func.similarity(models.CVInfo.level, lvl)
            for lvl in level
        ]).label('level_similarity')
        similarity_conditions.append((level_sim, WEIGHTS['level']))
        or_conditions.extend([
            func.similarity(models.CVInfo.level, lvl) >= SIMILARITY_THRESHOLD
            for lvl in level
        ])

    # Handle GPA range
    if point_range and len(point_range) == 2:
        if not any(isinstance(t, models.Education) for t in base_query._join_entities):
            base_query = base_query.join(models.Education)
        and_conditions.append(
            and_(
                models.Education.gpa.isnot(None),
                models.Education.gpa != "",
                cast(models.Education.gpa, Float).between(point_range[0], point_range[1])
            )
        )

    # Handle years of experience range
    if yoe_range and len(yoe_range) == 2:
        and_conditions.append(
            and_(
                models.CVInfo.yoe.isnot(None),
                models.CVInfo.yoe.between(yoe_range[0], yoe_range[1])
            )
        )

    # Build weighted score expression
    if similarity_conditions:
        score_terms = [
            expr * weight
            for expr, weight in similarity_conditions
        ]
        weighted_score = func.coalesce(sum(score_terms), 0.0).label('weighted_similarity')
    else:
        weighted_score = literal(1.0).label('weighted_similarity')

    # Add similarity expressions to query
    for expr, _ in similarity_conditions:
        base_query = base_query.add_columns(expr)
    base_query = base_query.add_columns(weighted_score)

    # Add filtering conditions
    if or_conditions:
        base_query = base_query.filter(or_(*or_conditions))
    if and_conditions:
        base_query = base_query.filter(and_(*and_conditions))

    # Important: Group by all non-aggregated columns
    group_by_columns = [
        models.CVInfo.id,
        models.CVInfo.file_id,
        models.CVInfo.user_id,
        models.CVInfo.full_name,
        models.CVInfo.industry,
        models.CVInfo.job_title,
        models.CVInfo.level,
        models.CVInfo.phone,
        models.CVInfo.address,
        models.CVInfo.city_province,
        models.CVInfo.country,
        models.CVInfo.date_of_birth,
        models.CVInfo.gender,
        models.CVInfo.linkedin,
        models.CVInfo.summary,
        models.CVInfo.yoe,
        models.CVInfo.skills,
        models.CVInfo.objectives,
        models.File.filename
    ]
    
    # Apply grouping and ordering
    final_query = base_query.group_by(*group_by_columns).order_by(desc('weighted_similarity'))

    # Execute query
    candidates = final_query.all()

    # Format results
    results = []
    seen_file_ids = set()  # Track seen file_ids

    for candidate in candidates:
        result = schemas.CVInfoResponse.from_orm(candidate[0]).dict()
        result["File Name"] = str(candidate[1])
        
        # Check if this file_id has been seen before
        file_id = result.get("file_id")
        if file_id in seen_file_ids:
            continue  # Skip this result as we've seen this file_id before
        
        seen_file_ids.add(file_id)  # Add to seen file_ids
        
        # Add similarity scores
        offset = 2  # Skip CVInfo and filename
        for i, (expr, _) in enumerate(similarity_conditions):
            result[expr.name] = float(candidate[offset + i]) if candidate[offset + i] is not None else 0.0
        
        # Add weighted similarity
        if similarity_conditions:
            result["weighted_similarity"] = float(candidate[-1]) if candidate[-1] is not None else 0.0
        
        results.append(result)

    # Sort deduped results by weighted similarity (if it exists)
    if results and "weighted_similarity" in results[0]:
        results.sort(key=lambda x: x.get("weighted_similarity", 0), reverse=True)
    
    print(f"Found {len(results)} unique results after deduplication")
    return results

@router.post("/fetch_cv_info")  # Changed to POST
async def fetch_cv_info(
    data: dict,  # Changed to accept a dict
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    folder_names = data.get("folder_names", [])
    print("Received folder names:", folder_names)  # Debug print
    
    if folder_names:
        folders = db.query(models.Folder).filter(
            models.Folder.user_id == current_user.id,
            func.lower(models.Folder.name).in_(map(str.lower, folder_names))
        ).all()
    else:
        folders = db.query(models.Folder).filter(
            models.Folder.user_id == current_user.id
        ).all()

    # Rest of your code remains the same
    if not folders:
        raise HTTPException(status_code=404, detail="No matching folders found")
    
    # Get file IDs from the folders
    file_ids = [file.id for folder in folders for file in folder.files]
    
    # Rest of your existing code...

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
    print(job_titles)
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

