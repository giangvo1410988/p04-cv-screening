from datetime import datetime
import models as models
from sqlalchemy.orm import Session

def safe_get(value):
    """Returns None if the value is an empty string or None, otherwise returns the value."""
    return value if value not in ("", None) else None


def insert_cv_data(db: Session, parsed_data: dict, file_id: int):
    try:
        # Handle empty strings or None for date_of_birth and other fields
        cv_info = models.CVInfo(
            file_id=file_id,
            full_name=parsed_data["personal_information"]["full_name"],
            industry=parsed_data["personal_information"]["industry"],
            job_title=parsed_data["personal_information"]["job_title"],
            level=safe_get(parsed_data["personal_information"]["level"]),
            phone=parsed_data["personal_information"]["phone"],
            address=parsed_data["personal_information"]["address"],
            city_province=parsed_data["personal_information"]["city/province"],
            country=parsed_data["personal_information"]["country"],
            date_of_birth=safe_get(parsed_data["personal_information"]["date_of_birth"]),
            gender=safe_get(parsed_data["personal_information"]["gender"]),
            linkedin=parsed_data["personal_information"]["linkedln"],
            skills=parsed_data["skills"],
            objectives=parsed_data["objectives"]
        )
        db.add(cv_info)
        db.commit()
        db.refresh(cv_info)

        # Insert Education entries
        if parsed_data.get("education"):  # Check if "education" exists and is not empty
            for edu in parsed_data["education"]:
                education = models.Education(
                    cv_info_id=cv_info.id,
                    degree=edu.get("degree", ""),  # Use .get() to handle missing keys
                    institution_name=edu.get("institution_name", ""),
                    major=edu.get("major", ""),
                    gpa=edu.get("gpa", ""),
                    start_time=parse_date(edu.get("start_time")),
                    end_time=parse_date(edu.get("end_time"))
                )
                db.add(education)

        # Insert Certificate entries (Language Certificates)
        if parsed_data.get("certificates", {}).get("language_certificates"):  # Ensure "certificates" exists
            for lang_cert in parsed_data["certificates"]["language_certificates"]:
                certificate = models.Certificate(
                    cv_info_id=cv_info.id,
                    certificate_name=lang_cert.get("certificate_name", ""),
                    certificate_point_level=lang_cert.get("certificate_point_level", ""),
                    start_time=parse_date(lang_cert.get("start_time")),
                    end_time=parse_date(lang_cert.get("end_time")),
                    language=lang_cert.get("language", "")
                )
                db.add(certificate)

        # Insert Other Certificates
        if parsed_data.get("certificates", {}).get("other_certificates"):
            for other_cert in parsed_data["certificates"]["other_certificates"]:
                certificate = models.Certificate(
                    cv_info_id=cv_info.id,
                    certificate_name=other_cert.get("certificate_name", ""),
                    certificate_point_level=other_cert.get("certificate_point", ""),
                    start_time=parse_date(other_cert.get("start_time")),
                    end_time=parse_date(other_cert.get("end_time"))
                )
                db.add(certificate)

        # Insert Project entries
        if parsed_data.get("projects"):
            for proj in parsed_data["projects"]:
                project = models.Project(
                    cv_info_id=cv_info.id,
                    project_name=proj.get("project_name", ""),
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
                    award_name=awd.get("award_name", ""),
                    time=parse_date(awd.get("time")),
                    description=awd.get("description", "")
                )
                db.add(award)

        # Insert Experience entries (Work Experience)
        if parsed_data.get("work_experience"):
            for exp in parsed_data["work_experience"]:
                experience = models.Experience(
                    cv_info_id=cv_info.id,
                    company_name=exp.get("company_name", ""),
                    job_title=exp.get("job_title", ""),
                    start_time=parse_date(exp.get("start_time")),
                    end_time=parse_date(exp.get("end_time")),
                    job_descriptions=exp.get("job_descriptions", []),
                    industry=exp.get("industry", ""),
                    company_location_city=exp.get("company_location", {}).get("city", ""),
                    company_location_country=exp.get("company_location", {}).get("country", "")
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

