import json
import datetime
import models

def safe_get(value):
    """Returns None if the value is an empty string or None, otherwise returns the value."""
    return value if value not in ("", None) else None

def parse_date(date_string: str) -> datetime.date:
    if not date_string:
        return None
    try:
        return datetime.strptime(date_string, "%Y-%m-%d").date()
    except ValueError:
        return None


def insert_cv_data(parsed_data: dict, file_id: int):
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
    # db.add(cv_info)
    # db.commit()
    # db.refresh(cv_info)
    # db.refresh(cv_info)

    # Insert Education entries
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
            # db.add(education)

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
            # db.add(certificate)

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
            # db.add(certificate)

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
            # db.add(project)

    # Insert Award entries
    if parsed_data.get("awards"):
        for awd in parsed_data["awards"]:
            award = models.Award(
                cv_info_id=cv_info.id,
                award_name=awd.get("award_name", ""),
                time=parse_date(awd.get("time")),
                description=awd.get("description", "")
            )
            # db.add(award)

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
            # db.add(experience)


    # db.commit()
data = {"personal_information":{"full_name":"Vu Quoc Thai Binh","industry":"Computer Science","job_title":"Machine Learning Engineer",
                                "level":"Graduate Student","phone":"0907664801","address":"","city/province":"Ho Chi Minh city","country":"",
                                "date_of_birth":"","gender":"","linkedln":""},
                                "skills":["Python","C","C++","Bash","HTML/CSS/Javascript","PyTorch","TensorFlow","Keras","OpenCV","PaddleOCR","NumPy","scikit-learn","Matplotlib","PySpark","Flask","MySQL","Kafka","Spark","MLflow","Kubeflow","Docker","Kubernetes","CI/CD pipelines","Model versioning","Model monitoring"],
                                "education":[{"degree":"Bachelor of Computer Science","institution_name":"University of Information Technology","major":"","gpa":"7.91/10","start_time":"","end_time":""}],
                                "certificates":{"language_certificates":[{"language":"English","certificate_name":"IELTS","certificate_point_level":"6.0","start_time":"","end_time":""}],
                                                "other_certificates":[{"certificate_name":"IBM DevOps and Software Engineering","certificate_point":"","start_time":"","end_time":""},
                                                                      {"certificate_name":"DeepLearning.AI Machine Learning Engineering for Production (MLOps) Specialization","certificate_point":"","start_time":"","end_time":""},
                                                                      {"certificate_name":"MOS WORD","certificate_point":"","start_time":"","end_time":""},
                                                                      {"certificate_name":"MOS EXCEL","certificate_point":"","start_time":"","end_time":""}]},
                                                "projects":[{"project_name":"Automatic License Plate Recognition ALPR","start_time":"","end_time":"","detailed_descriptions":["ALPR system designed to identify various vehicles and their corresponding license plates","Using YOLOv8 to detect vehicles, WPOD-NET to detect license plate and PaddleOCR to extract data from the license plates","Technologies : YOLOv8, WPOD-NET, PaddleOCR, Pytorch, OpenCV","Code Repository"]},
                                                {"project_name":"Food ingredients detection","start_time":"","end_time":"","detailed_descriptions":["Developed a computer vision system using YOLOv8 to identify and classify 13 common food ingredients","Re-trained a YOLOv8 object detection model for the specific task of identifying and classifying 13 food ingredients","Technologies : YOLOv8, OpenCV, Flask, Pytorch","Code Repository"]},
                                                {"project_name":"Face Swap","start_time":"","end_time":"","detailed_descriptions":["Using various methods to replace a person’s face in an image or video with another person’s face","dlib (68 landmarks, basic algorithm)","dlib (81 landmarks, Delaunay triangulation)","MediaPipe (Delaunay triangulation)","MediaPipe + OpenGL (Delaunay triangulation)","Technologies : OpenCV, Mediapipe, Dlib, OpenGL, numpy","Code Repository"]},
                                                {"project_name":"SmartSight","start_time":"","end_time":"","detailed_descriptions":["Leverages machine learning to analyze your movements through a camera, creating a personalized smart home experience that automatically adjusts lighting, temperature, and more based on your activities (reading, working, sleeping)","Technologies : YOLOv8, Pytorch, OpenCV"]}],
                                                "objectives":"AI-focused Computer Science graduate student with a strong foundation in Computer Vision, NLP, and Deep Learning. Seeks a Machine Learning Engineer position to apply knowledge and contribute to innovative AI solutions across various industries.","awards":[]}

print(insert_cv_data(parsed_data=data,file_id=1))