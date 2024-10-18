from datetime import datetime
import models as models
from sqlalchemy.orm import Session
from .ai import generate_embedding, api_key

def safe_get(value):
    """Returns None if the value is an empty string or None, otherwise returns the value."""
    return value if value not in ("", None) else None

def insert_cv_data(db: Session, parsed_data: dict, file_id: int):
    try:
        # Handle empty strings or None for date_of_birth and other fields
        cv_info = models.CVInfo(
            file_id=file_id,
            full_name=parsed_data["personal_information"].get("full_name"),
            industry=parsed_data["personal_information"].get("industry"),
            job_title=parsed_data["personal_information"].get("job_title"),
            level=safe_get(parsed_data["personal_information"].get("level")),
            phone=parsed_data["personal_information"].get("phone"),
            address=parsed_data["personal_information"].get("address"),
            city_province=parsed_data["personal_information"].get("city/province"),
            country=parsed_data["personal_information"].get("country"),
            date_of_birth=safe_get(parsed_data["personal_information"].get("date_of_birth")),
            gender=safe_get(parsed_data["personal_information"].get("gender")),
            linkedin=parsed_data["personal_information"].get("linkedln"),
            skills=parsed_data.get("skills", []),  # Use an empty list if no skills are provided
            objectives=parsed_data.get("objectives"),
            yoe=parsed_data["personal_information"].get("yoe")
        )

        # Generate embedding
        # Prepare the text to generate embedding
        embedding_input_parts = []

        # Add job title, objectives, and skills
        if cv_info.job_title:
            embedding_input_parts.append(cv_info.job_title)
        if cv_info.objectives:
            embedding_input_parts.append(cv_info.objectives)
        if cv_info.skills:
            embedding_input_parts.extend(cv_info.skills)

        # Add work experience
        work_experiences = parsed_data.get("work_experience", [])
        for exp in work_experiences:
            if exp.get("job_title"):
                embedding_input_parts.append(exp["job_title"])
            if exp.get("company_name"):
                embedding_input_parts.append(exp["company_name"])
            if exp.get("job_descriptions"):
                embedding_input_parts.extend(exp["job_descriptions"])
            if exp.get("achievements"):
                embedding_input_parts.extend(exp["achievements"])

        # Add projects
        projects = parsed_data.get("projects", [])
        for proj in projects:
            if proj.get("project_name"):
                embedding_input_parts.append(proj["project_name"])
            if proj.get("detailed_descriptions"):
                embedding_input_parts.extend(proj["detailed_descriptions"])

        # Add education
        educations = parsed_data.get("education", [])
        for edu in educations:
            if edu.get("degree"):
                embedding_input_parts.append(edu["degree"])
            if edu.get("institution_name"):
                embedding_input_parts.append(edu["institution_name"])
            if edu.get("major"):
                embedding_input_parts.append(edu["major"])

        # Add certifications
        # Language certificates
        language_certs = parsed_data.get("certificates", {}).get("language_certificates", [])
        for cert in language_certs:
            if cert.get("certificate_name"):
                embedding_input_parts.append(cert["certificate_name"])
            if cert.get("certificate_point_level"):
                embedding_input_parts.append(cert["certificate_point_level"])
            if cert.get("language"):
                embedding_input_parts.append(cert["language"])

        # Other certificates
        other_certs = parsed_data.get("certificates", {}).get("other_certificates", [])
        for cert in other_certs:
            if cert.get("certificate_name"):
                embedding_input_parts.append(cert["certificate_name"])
            if cert.get("certificate_point"):
                embedding_input_parts.append(cert["certificate_point"])

        # Combine all parts into a single string
        embedding_input = ' '.join(str(part) for part in embedding_input_parts if part)

        # Generate the embedding vector if there's input text
        if embedding_input.strip():
            try:
                cv_info.embedding_vector = generate_embedding(embedding_input, api_key=api_key)
            except Exception as e:
                print(f"Failed to generate embedding for file_id {file_id}: {e}")
                cv_info.embedding_vector = None
        else:
            cv_info.embedding_vector = None

        db.add(cv_info)
        db.commit()
        db.refresh(cv_info)

        # Insert Education entries
        if educations:
            for edu in educations:
                education = models.Education(
                    cv_info_id=cv_info.id,
                    degree=edu.get("degree"),
                    institution_name=edu.get("institution_name"),
                    major=edu.get("major"),
                    gpa=edu.get("gpa"),
                    start_time=parse_date(edu.get("start_time")),
                    end_time=parse_date(edu.get("end_time"))
                )
                db.add(education)

        # Insert Certificate entries (Language Certificates)
        if language_certs:
            for lang_cert in language_certs:
                certificate = models.Certificate(
                    cv_info_id=cv_info.id,
                    certificate_name=lang_cert.get("certificate_name"),
                    certificate_point_level=lang_cert.get("certificate_point_level"),
                    start_time=parse_date(lang_cert.get("start_time")),
                    end_time=parse_date(lang_cert.get("end_time")),
                    language=lang_cert.get("language")
                )
                db.add(certificate)

        # Insert Other Certificates
        if other_certs:
            for other_cert in other_certs:
                certificate = models.Certificate(
                    cv_info_id=cv_info.id,
                    certificate_name=other_cert.get("certificate_name"),
                    certificate_point_level=other_cert.get("certificate_point"),
                    start_time=parse_date(other_cert.get("start_time")),
                    end_time=parse_date(other_cert.get("end_time"))
                )
                db.add(certificate)

        # Insert Project entries
        if projects:
            for proj in projects:
                project = models.Project(
                    cv_info_id=cv_info.id,
                    project_name=proj.get("project_name"),
                    start_time=parse_date(proj.get("start_time")),
                    end_time=parse_date(proj.get("end_time")),
                    detailed_descriptions=proj.get("detailed_descriptions", [])
                )
                db.add(project)

        # Insert Award entries
        if parsed_data.get("awards"):
            for awd in parsed_data["awards"]:
                award = models.Award(
                    cv_info_id=cv_info.id,
                    award_name=awd.get("award_name"),
                    time=parse_date(awd.get("time")),
                    description=awd.get("description")
                )
                db.add(award)

        # Insert Experience entries (Work Experience)
        if work_experiences:
            for exp in work_experiences:
                experience = models.Experience(
                    cv_info_id=cv_info.id,
                    company_name=exp.get("company_name"),
                    job_title=exp.get("job_title"),
                    start_time=parse_date(exp.get("start_time")),
                    end_time=parse_date(exp.get("end_time")),
                    detailed_working_description=exp.get("job_descriptions", []),
                    working_industry=exp.get("industry"),
                    achievements=exp.get("achievements", []),
                    level=exp.get("level"),
                )
                db.add(experience)

        # Commit all entries
        db.commit()

    except Exception as e:
        db.rollback()  # Rollback any changes made in case of an error

        # Update the file status to "failed"
        db_file = db.query(models.File).filter(models.File.id == file_id).first()
        if db_file:
            db_file.status = "failed"
            db.commit()

        # Optionally log the error
        print(f"Failed to insert CV data for file_id {file_id}: {e}")


def parse_date(date_string: str) -> datetime.date:
    if not date_string:
        return None
    try:
        return datetime.strptime(date_string, "%Y-%m-%d").date()
    except ValueError:
        return None

