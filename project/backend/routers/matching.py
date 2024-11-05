from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
import models
import schemas
from database import get_db
from routers.auth import get_current_user
from sqlalchemy import cast, Float, or_, func, and_
import typesense
from pathlib import Path
import PyPDF2
from . import ai
from .ai import generate_embedding
import json
import openai
import numpy as np

router = APIRouter(prefix="/matching", tags=["matching"])
UPLOAD_DIR = Path("static/upload_job_descriptions")

# Initialize Typesense client
client = typesense.Client({
    'nodes': [{
        'host': 'localhost',
        'port': '8108',
        'protocol': 'http'
    }],
    'api_key': 'aivision',  # Replace with your actual API key
    'connection_timeout_seconds': 2
})

def serialize_candidate(candidate):
    # Use the CVInfoResponse schema to serialize the candidate
    return schemas.CVInfoResponse.from_orm(candidate).dict()

# Helper function to calculate cosine similarity between two vectors
def cosine_similarity(a, b, epsilon=1e-10):
    a_norm = np.linalg.norm(a)
    b_norm = np.linalg.norm(b)
    if a_norm < epsilon or b_norm < epsilon:
        return 0.0
    return np.dot(a, b) / (a_norm * b_norm)

# Helper functions first
def prepare_query_text(search_request: schemas.HybridSearchRequest) -> str:
    """Build query text from search request fields."""
    query_parts = []

    def add_to_query(text):
        if text and isinstance(text, (str, int, float)):
            query_parts.append(str(text))
        elif isinstance(text, list):
            query_parts.extend([str(item) for item in text if item])

    # Add relevant fields
    if search_request.job_title:
        add_to_query(f"job title: {search_request.job_title}")
    if search_request.industry:
        add_to_query(f"industry: {search_request.industry}")
    
    if search_request.location:
        if search_request.location.city:
            add_to_query(f"city: {search_request.location.city}")
        if search_request.location.country:
            add_to_query(f"country: {search_request.location.country}")
    
    if search_request.job_requirements:
        if search_request.job_requirements.skills:
            add_to_query(f"skills: {', '.join(search_request.job_requirements.skills)}")
        if search_request.job_requirements.languages:
            add_to_query(f"languages: {', '.join(search_request.job_requirements.languages)}")
        if search_request.job_requirements.education:
            if search_request.job_requirements.education.degree:
                add_to_query(f"degree: {search_request.job_requirements.education.degree}")
            if search_request.job_requirements.education.major:
                add_to_query(f"major: {search_request.job_requirements.education.major}")

    return " . ".join(query_parts).strip() or "general candidate search"

def setup_typesense_collection(user_id: int):
    """Setup or retrieve Typesense collection for user."""
    collection_name = f"candidates_{user_id}"
    schema = {
        "name": collection_name,
        "fields": [
            {"name": "id", "type": "string"},
            {"name": "job_title", "type": "string"},
            {"name": "industry", "type": "string"},
            {"name": "location_city", "type": "string"},
            {"name": "location_country", "type": "string"},
            {"name": "skills", "type": "string[]"},
            {"name": "languages", "type": "string[]"},
            {"name": "degree", "type": "string"},
            {"name": "major", "type": "string"},
            {"name": "level", "type": "string"},
            {"name": "gpa", "type": "float"},
            {"name": "years_of_experience", "type": "int32"},
        ],
        "default_sorting_field": "years_of_experience"
    }

    try:
        client.collections[collection_name].retrieve()
    except typesense.exceptions.ObjectNotFound:
        client.collections.create(schema)
    
    return collection_name

def fetch_candidates(db: Session, user_id: int, folder_names: List[str]):
    """Fetch candidates from specified folders."""
    query = db.query(models.CVInfo).join(
        models.File, models.CVInfo.file_id == models.File.id
    ).join(
        models.Folder, models.File.folder_id == models.Folder.id
    ).filter(
        models.Folder.user_id == user_id,
        func.lower(models.Folder.name).in_([name.lower() for name in folder_names])
    ).options(
        joinedload(models.CVInfo.education),
        joinedload(models.CVInfo.experience),
        joinedload(models.CVInfo.certificates),
        joinedload(models.CVInfo.projects),
        joinedload(models.CVInfo.awards)
    )
    return query.all()

def prepare_candidate_for_indexing(candidate):
    """Convert candidate to format for Typesense indexing."""
    return {
        "id": str(candidate.id),
        "job_title": candidate.job_title or "",
        "industry": candidate.industry or "",
        "location_city": candidate.city_province or "",
        "location_country": candidate.country or "",
        "skills": candidate.skills or [],
        "languages": [],
        "degree": candidate.education[0].degree if candidate.education else "",
        "major": candidate.education[0].major if candidate.education else "",
        "level": candidate.level or "",
        "gpa": float(candidate.education[0].gpa) if (candidate.education and candidate.education[0].gpa) else 0.0,
        "years_of_experience": candidate.yoe or 0,
    }

def get_match_details(candidate, search_request):
    """Calculate detailed matching information for a candidate."""
    return {
        "matching_skills": [
            skill for skill in (candidate.skills or [])
            if search_request.job_requirements and 
            search_request.job_requirements.skills and
            any(s.lower() in skill.lower() for s in search_request.job_requirements.skills)
        ],
        "education_match": any(
            edu.degree.lower() == search_request.job_requirements.education.degree.lower()
            for edu in candidate.education
        ) if (search_request.job_requirements and 
             search_request.job_requirements.education and 
             search_request.job_requirements.education.degree and 
             candidate.education) else False,
        "job_title_similarity": 0.0,  # Will be updated with actual similarity
        "industry_match": (
            candidate.industry.lower() == search_request.industry.lower()
            if search_request.industry and candidate.industry
            else False
        )
    }

def calculate_summary_stats(response_data, combined_results):
    """Calculate summary statistics for search results."""
    return {
        "total_candidates": len(combined_results),
        "unique_candidates": len(response_data),
        "avg_similarity": sum(c.get('ranking_scores', {}).get('weighted_similarity', 0) 
                            for c in response_data) / len(response_data) if response_data else 0,
        "max_similarity": max((c.get('ranking_scores', {}).get('weighted_similarity', 0) 
                             for c in response_data), default=0),
        "skills_coverage": sum(len(c.get('match_details', {}).get('matching_skills', [])) 
                             for c in response_data) / len(response_data) if response_data else 0
    }

@router.post("/hybrid_search")
async def hybrid_search_candidates(
    request: dict,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    """Main function for hybrid search of candidates."""
    # Extract folder names and validate request
    folder_names = request.pop('folder_names', [])
    if not folder_names:
        raise HTTPException(status_code=400, detail="Folder names are required")

    try:
        search_request = schemas.HybridSearchRequest(**request)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid request format: {str(e)}")

    # Prepare search components
    query_text = prepare_query_text(search_request)
    collection_name = setup_typesense_collection(current_user.id)
    
    # Fetch and prepare candidates
    candidates = fetch_candidates(db, current_user.id, folder_names)
    if not candidates:
        return {"results": [], "stats": {}, "query_info": {"search_text": query_text, "total_results": 0}}

    # Index candidates in Typesense
    candidates_data = [prepare_candidate_for_indexing(c) for c in candidates]
    try:
        documents = "\n".join([json.dumps(candidate) for candidate in candidates_data])
        client.collections[collection_name].documents.import_(documents, {'action': 'upsert'})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error indexing data: {e}")

    # Generate embeddings and perform searches
    try:
        query_embedding = generate_embedding(query_text, api_key=ai.api_key)
        
        # Perform text search
        text_results = client.collections[collection_name].documents.search({
            "q": query_text,
            "query_by": "job_title,industry,location_city,location_country,skills,languages,degree,major,level",
            "query_by_weights": "2,2,1,1,3,1,1,1,1,",
            "num_typos": 2,
            "operator": "or",
            "per_page": 100,
            "sort_by": "years_of_experience:desc",
        })
        full_text_results = [(hit['text_match'], hit['document']) for hit in text_results.get('hits', [])]
        
        # Perform semantic search
        similarity_scores = []
        for candidate in candidates:
            if candidate.embedding_vector:
                score = cosine_similarity(query_embedding, np.array(candidate.embedding_vector))
                similarity_scores.append((score, candidate))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Combine and rank results
    similarity_scores.sort(key=lambda x: x[0], reverse=True)
    combined_results = merge_and_rank_results(full_text_results, similarity_scores)

    # Prepare final response
    response_data = []
    seen_file_ids = set()

    for result in combined_results:
        candidate_id = int(result['id'])
        candidate = next((c for c in candidates if c.id == candidate_id), None)
        if candidate and candidate.file_id not in seen_file_ids:
            seen_file_ids.add(candidate.file_id)
            
            serialized = serialize_candidate(candidate)
            serialized.update({
                "ranking_scores": {
                    "text_match_score": result.get('text_match', 0.0),
                    "semantic_score": next((score for score, c in similarity_scores if c.id == candidate_id), 0.0),
                    "weighted_similarity": result.get('weighted_similarity', 0.0),
                    "years_of_experience": candidate.yoe or 0
                },
                "match_details": get_match_details(candidate, search_request)
            })
            response_data.append(serialized)

    # Prepare final response
    return {
        "results": response_data,
        "stats": calculate_summary_stats(response_data, combined_results),
        "query_info": {
            "search_text": query_text,
            "total_results": len(response_data)
        }
    }

def merge_and_rank_results(full_text_results, embedding_results, alpha=0.5):
    """
    Merges and ranks results from full-text search and embedding similarity scores.
    Parameters:
        full_text_results: List of tuples (score, candidate_data)
        embedding_results: List of tuples (score, candidate_data)
        alpha: Weighting factor between 0 and 1
    """
    # Normalize scores
    max_full_text_score = max([score for score, _ in full_text_results], default=1)
    max_embedding_score = max([score for score, _ in embedding_results], default=1)

    # Create a dictionary to hold combined scores
    combined_scores = {}

    # Add full-text scores to combined_scores
    for score, candidate_data in full_text_results:
        candidate_id = candidate_data['id']
        normalized_score = (score / max_full_text_score) * alpha
        combined_scores[candidate_id] = {'data': candidate_data, 'score': normalized_score}

    # Add embedding scores to combined_scores
    for score, candidate_data in embedding_results:
        candidate_id = str(candidate_data.id)
        normalized_score = (score / max_embedding_score) * (1 - alpha)
        if candidate_id in combined_scores:
            combined_scores[candidate_id]['score'] += normalized_score
        else:
            combined_scores[candidate_id] = {'data': {'id': candidate_id}, 'score': normalized_score}

    # Sort combined results
    sorted_results = sorted(combined_scores.values(), key=lambda x: x['score'], reverse=True)

    # Return the sorted candidate data (only IDs for now)
    return [result['data'] for result in sorted_results]


# Parsing job descriptions using PyPDF2 and AI prompt
def parse_job_description(file_path: Path):
    with open(file_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        job_description_text = ""
        for page in pdf_reader.pages:
            job_description_text += page.extract_text()

    prompt = ai.prompt_job_description(job_description_text)
    response, _, _ = ai.call_openAI(prompt, ai.api_key)

    if "```" in response:
        response = response.split("```")[1].strip("json")

    try:
        data_dict = json.loads(response)
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
        return None

    return data_dict


# API to upload and parse job description PDF
@router.post("/parse")
async def upload_and_parse_job_description(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    if not UPLOAD_DIR.exists():
        UPLOAD_DIR.mkdir(parents=True)

    file_path = UPLOAD_DIR / file.filename

    with open(file_path, "wb") as buffer:
        buffer.write(file.file.read())

    job_description_data = parse_job_description(file_path)

    if not job_description_data:
        raise HTTPException(status_code=500, detail="Failed to extract information from the job description PDF.")

    return job_description_data


# # API to handle user-specific candidates with Typesense
# @router.post("/user_specific_candidates")
# async def search_candidates(
#     job_title: Optional[List[str]] = None,
#     current_job: Optional[List[str]] = None,
#     industry: Optional[List[str]] = None,
#     city: Optional[str] = None,
#     country: Optional[str] = None,
#     old_range: Optional[List[int]] = None,
#     language: Optional[List[str]] = None,
#     skill: Optional[List[str]] = None,
#     degree: Optional[str] = None,
#     major: Optional[str] = None,
#     level: Optional[List[str]] = None,
#     point_range: Optional[List[float]] = None,
#     yoe_range: Optional[List[int]] = None,
#     folder_names: Optional[List[str]] = None,
#     db: Session = Depends(get_db),
#     current_user: schemas.User = Depends(get_current_user)
# ):
#     collection_name = "candidates"

#     # Ensure the collection exists (create if not)
#     schema = {
#         "name": collection_name,
#         "fields": [
#             {"name": "id", "type": "string"},
#             {"name": "user_id", "type": "int32"},
#             {"name": "job_title", "type": "string"},
#             {"name": "industry", "type": "string"},
#             {"name": "location_city", "type": "string"},
#             {"name": "location_country", "type": "string"},
#             {"name": "skills", "type": "string[]"},
#             {"name": "languages", "type": "string[]"},
#             {"name": "degree", "type": "string"},
#             {"name": "major", "type": "string"},
#             {"name": "level", "type": "string"},
#             {"name": "gpa", "type": "float"},
#             {"name": "years_of_experience", "type": "int32"},
#         ],
#         "default_sorting_field": "years_of_experience"
#     }

#     # Create collection if it doesn't exist
#     try:
#         client.collections[collection_name]
#     except typesense.exceptions.ObjectNotFound:
#         client.collections.create(schema)

#     # Fetch candidates from the database
#     try:
#         query = db.query(models.CVInfo).filter(models.CVInfo.user_id == current_user.id)

#         # Apply filters based on the provided parameters
#         if job_title:
#             job_title_filters = [models.CVInfo.job_title.ilike(f"%{jt}%") for jt in job_title]
#             query = query.filter(or_(*job_title_filters))
#         # ... other filters ...

#         candidates = query.all()
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error fetching candidates: {e}")

#     # Prepare data for indexing
#     candidates_data = []
#     for candidate in candidates:
#         candidate_data = {
#             "id": str(candidate.id),
#             "user_id": candidate.user_id,
#             "job_title": candidate.job_title or "",
#             "industry": candidate.industry or "",
#             "location_city": candidate.city_province or "",
#             "location_country": candidate.country or "",
#             "skills": candidate.skills or [],
#             "languages": [],  # Add languages if available
#             "degree": candidate.education[0].degree if candidate.education else "",
#             "major": candidate.education[0].major if candidate.education else "",
#             "level": candidate.level or "",
#             "gpa": float(candidate.education[0].gpa) if candidate.education and candidate.education[0].gpa else 0.0,
#             "years_of_experience": candidate.yoe or 0,
#         }
#         candidates_data.append(candidate_data)

#     # Index data into Typesense using bulk import
#     try:
#         # Prepare data in JSONL format
#         documents = "\n".join([json.dumps(candidate) for candidate in candidates_data])
#         client.collections[collection_name].documents.import_(documents)
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error indexing data: {e}")

#     # Construct the search query
#     search_parameters = {
#         "q": job_title[0] if job_title else "*",
#         "query_by": "job_title,industry,skills,degree,major",
#         "filter_by": f"user_id:={current_user.id}",
#         "per_page": 100,  # Adjust as needed
#     }

#     # Add additional filters
#     if level:
#         levels = ','.join(level)
#         search_parameters["filter_by"] += f" && level:=[{levels}]"

#     if point_range and len(point_range) == 2:
#         search_parameters["filter_by"] += f" && gpa:>={point_range[0]} && gpa:<={point_range[1]}"

#     # Perform the search
#     try:
#         search_results = client.collections[collection_name].documents.search(search_parameters)
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error during search: {e}")

#     # Return the search results to the user
#     return search_results