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
    'api_key': 'typesensemulti',  # Replace with your actual API key
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

@router.post("/hybrid_search")
async def hybrid_search_candidates(
    request: schemas.HybridSearchRequest,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    query_parts = []

    # Add parts of the query based on the request fields
    if request.job_title:
        query_parts.append(request.job_title)
    if request.industry:
        query_parts.append(request.industry)
    if request.location and request.location.city:
        query_parts.append(request.location.city)
    if request.location and request.location.country:
        query_parts.append(request.location.country)
    if request.job_requirements and request.job_requirements.skills:
        query_parts.extend(request.job_requirements.skills)
    if request.job_requirements and request.job_requirements.languages:
        query_parts.extend(request.job_requirements.languages)
    if request.job_requirements and request.job_requirements.education:
        if request.job_requirements.education.degree:
            query_parts.append(request.job_requirements.education.degree)
        if request.job_requirements.education.major:
            query_parts.append(request.job_requirements.education.major)

    # Join all parts of the query with spaces
    query = " ".join(query_parts)

    
    # Use per-user collection
    collection_name = f"candidates_{current_user.id}"
    # Define the schema without 'user_id'
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

    # Create collection if it doesn't exist
    try:
        client.collections[collection_name].retrieve()
    except typesense.exceptions.ObjectNotFound:
        try:
            client.collections.create(schema)
            print(f"Collection '{collection_name}' created successfully.")
        except Exception as e:
            print(f"Failed to create collection: {e}")
            raise HTTPException(status_code=500, detail=f"Error creating collection: {e}")
    except Exception as e:
        print(f"Error retrieving collection: {e}")
        raise HTTPException(status_code=500, detail=f"Error accessing collection: {e}")

    # Fetch candidates from the database
    try:
        # Step 1: Get folder IDs for the current user
        folder_ids = db.query(models.Folder.id).filter(models.Folder.user_id == current_user.id).all()
        folder_ids = [id for (id,) in folder_ids]  # Unpack tuples

        if not folder_ids:
            return {"results": []}  # No folders for the user

        # Step 2: Get file IDs in those folders
        file_ids = db.query(models.File.id).filter(models.File.folder_id.in_(folder_ids)).all()
        file_ids = [id for (id,) in file_ids]

        if not file_ids:
            return {"results": []}  # No files in the user's folders

        # Step 3: Get CVInfo entries associated with those file IDs
        candidates = db.query(models.CVInfo).filter(models.CVInfo.file_id.in_(file_ids)).all()

        if not candidates:
            return {"results": []}  # No CVInfo entries associated with the user's files

    except Exception as e:
        print(f"Error fetching candidates: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching candidates: {e}")

    # Prepare data for indexing
    candidates_data = []

    for candidate in candidates:
        candidate_data = {
            "id": str(candidate.id),
            "job_title": candidate.job_title or "",
            "industry": candidate.industry or "",
            "location_city": candidate.city_province or "",
            "location_country": candidate.country or "",
            "skills": candidate.skills or [],
            "languages": [],  # Add languages if available
            "degree": candidate.education[0].degree if candidate.education and len(candidate.education) > 0 else "",
            "major": candidate.education[0].major if candidate.education and len(candidate.education) > 0 else "",
            "level": candidate.level or "",
            "gpa": float(candidate.education[0].gpa) if candidate.education and len(candidate.education) > 0 and candidate.education[0].gpa else 0.0,
            "years_of_experience": candidate.yoe or 0,
        }
        candidates_data.append(candidate_data)

    # Index data into Typesense using bulk import
    try:
        # Prepare data in JSONL format
        documents = "\n".join([json.dumps(candidate) for candidate in candidates_data])
        import_response = client.collections[collection_name].documents.import_(
            documents,
            {'action': 'upsert'}  # Use 'upsert' to update existing records
        )
        # Check import response for errors
        for line in import_response.split('\n'):
            if line.strip():
                result = json.loads(line)
                if not result.get('success', False):
                    print(f"Error importing document ID {result.get('id')}: {result.get('error')}")
    except Exception as e:
        print(f"Error indexing data: {e}")
        raise HTTPException(status_code=500, detail=f"Error indexing data: {e}")

    # Step 1: Generate the embedding on the server
    try:
        query_embedding = generate_embedding(query, api_key=ai.api_key)
    except Exception as e:
        print(f"Error generating query embedding: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating query embedding: {e}")

    # Step 2: Perform full-text search in Typesense
    search_query = {
        "q": query,  # Dynamically constructed from the request
        "query_by": "job_title,industry,location_city,location_country,skills,languages,degree,major,level",
        "num_typos": 2,
        "query_by_weights": "2,2,1,1,3,1,1,1,1,",
        "operator": "or",
        "per_page": 100,
        "sort_by": "years_of_experience:desc",
    }


    try:
        full_text_response = client.collections[collection_name].documents.search(search_query)
        full_text_results = [
            (hit['text_match'], hit['document'])
            for hit in full_text_response.get('hits', [])
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error during full-text search: {e}")

    # Generate embeddings based on the request data (e.g., job_title, skills)
    try:
        query_embedding = generate_embedding(query, api_key=ai.api_key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating query embedding: {e}")


    # Step 3: Retrieve candidate embeddings and data from the database
    try:
        # Use the candidates fetched earlier
        candidates_embeddings = []
        candidates_data_list = []
        for candidate in candidates:
            if candidate.embedding_vector:
                candidate_embedding = np.array(candidate.embedding_vector)
                candidates_embeddings.append(candidate_embedding)
                candidates_data_list.append(candidate)
    except Exception as e:
        print(f"Error retrieving candidate embeddings: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving candidate embeddings: {e}")

    # Step 4: Perform embedding-based similarity search
    similarity_scores = []
    for candidate_embedding, candidate_data in zip(candidates_embeddings, candidates_data_list):
        score = cosine_similarity(query_embedding, candidate_embedding)
        similarity_scores.append((score, candidate_data))

    # Sort candidates based on similarity score
    similarity_scores.sort(key=lambda x: x[0], reverse=True)

    # Step 5: Combine and rank results from both full-text and embedding-based search
    combined_results = merge_and_rank_results(full_text_results, similarity_scores)

    # Step 6: Fetch detailed candidate data based on IDs
    candidate_ids = [int(candidate['id']) for candidate in combined_results]
    detailed_candidates = db.query(models.CVInfo).options(
        joinedload(models.CVInfo.education),
        joinedload(models.CVInfo.experience),
        joinedload(models.CVInfo.certificates),
        joinedload(models.CVInfo.projects),
        joinedload(models.CVInfo.awards)
    ).filter(models.CVInfo.id.in_(candidate_ids)).all()

    # Map candidate IDs to detailed data
    candidate_details_map = {candidate.id: candidate for candidate in detailed_candidates}

    # Prepare response data
    response_data = []
    for candidate in combined_results:
        candidate_id = int(candidate['id'])
        if candidate_id in candidate_details_map:
            detailed_candidate = candidate_details_map[candidate_id]
            serialized_candidate = serialize_candidate(detailed_candidate)
            response_data.append(serialized_candidate)
        else:
            print(f"Candidate ID {candidate_id} not found in detailed data.")

    return {"results": response_data}

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