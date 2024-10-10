from datetime import datetime
import models
from sqlalchemy.orm import Session

def insert_cv_data(db: Session, parsed_data: dict, file_id: int):
    # Create CVInfo entry
    cv_info = models.CVInfo(
        file_id=file_id,
        full_name=parsed_data["personal_information"]["full_name"],
        industry=parsed_data["personal_information"]["industry"],
        job_title=parsed_data["personal_information"]["job_title"],
        level=parsed_data["personal_information"]["level"],
        phone=parsed_data["personal_information"]["phone"],
        address=parsed_data["personal_information"]["address"],
        city_province=parsed_data["personal_information"]["city/province"],
        country=parsed_data["personal_information"]["country"],
        date_of_birth=parsed_data["personal_information"]["date_of_birth"],
        gender=parsed_data["personal_information"]["gender"],
        linkedin=parsed_data["personal_information"]["linkedln"],
        skills=parsed_data["skills"],
        objectives=parsed_data["objectives"]
    )
    db.add(cv_info)
    db.commit()
    db.refresh(cv_info)

    # Insert Education entries
    for edu in parsed_data["education"]:
        education = models.Education(
            cv_info_id=cv_info.id,
            degree=edu["degree"],
            institution_name=edu["institution_name"],
            major=edu["major"],
            gpa=edu["gpa"],
            start_time=parse_date(edu["start_time"]),
            end_time=parse_date(edu["end_time"])
        )
        db.add(education)

    # Insert Certificate entries
    for lang_cert in parsed_data["certificates"]["language_certificates"]:
        certificate = models.Certificate(
            cv_info_id=cv_info.id,
            certificate_name=lang_cert["certificate_name"],
            certificate_point_level=lang_cert["certificate_point_level"],
            start_time=parse_date(lang_cert["start_time"]),
            end_time=parse_date(lang_cert["end_time"]),
            language=lang_cert["language"]
        )
        db.add(certificate)
    
    for other_cert in parsed_data["certificates"]["other_certificates"]:
        certificate = models.Certificate(
            cv_info_id=cv_info.id,
            certificate_name=other_cert["certificate_name"],
            certificate_point=other_cert["certificate_point"],
            start_time=parse_date(other_cert["start_time"]),
            end_time=parse_date(other_cert["end_time"])
        )
        db.add(certificate)

    # Insert Project entries
    for proj in parsed_data["projects"]:
        project = models.Project(
            cv_info_id=cv_info.id,
            project_name=proj["project_name"],
            start_time=parse_date(proj["start_time"]),
            end_time=parse_date(proj["end_time"]),
            detailed_descriptions=proj["detailed_descriptions"]
        )
        db.add(project)

    # Insert Award entries
    for awd in parsed_data["awards"]:
        award = models.Award(
            cv_info_id=cv_info.id,
            award_name=awd["award_name"],
            time=parse_date(awd["time"]),
            description=awd["description"]
        )
        db.add(award)

    # Insert Experience entries (from prompt_experience)
    for exp in parsed_data["work_experience"]:
        experience = models.Experience(
            cv_info_id=cv_info.id,
            company_name=exp["company_name"],
            job_title=exp["job_title"],
            start_time=parse_date(exp["start_time"]),
            end_time=parse_date(exp["end_time"]),
            job_descriptions=exp["job_descriptions"],
            industry=exp["industry"],
            company_location_city=exp["company_location"]["city"],
            company_location_country=exp["company_location"]["country"]
        )
        db.add(experience)

    db.commit()


def parse_date(date_string: str) -> datetime.date:
    if not date_string:
        return None
    try:
        return datetime.strptime(date_string, "%Y-%m-%d").date()
    except ValueError:
        return None

