from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, Enum, Boolean, JSON, Text, Date
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
import datetime
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

from database import Base
from schemas import Role

class User(Base):
    __tablename__ = "users"  # Changed from "user" to "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    point = Column(Integer, default=0)
    phone = Column(String, default="0981234567")
    role = Column(Enum(Role), default=Role.ENDUSER)
    is_activated = Column(Boolean, default=False)
    otp = Column(String, nullable=True)

    folders = relationship("Folder", back_populates="owner")
    cv_info = relationship("CVInfo", uselist=False, back_populates="user")

class Folder(Base):
    __tablename__ = "folders"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))

    owner = relationship("User", back_populates="folders")
    files = relationship("File", back_populates="folder")
    jobs = relationship("JobManagement", back_populates="folder")  


class File(Base):
    __tablename__ = "files"  # Changed from "file" to "files"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    uploaded_date = Column(DateTime, default=datetime.datetime.utcnow)
    file_type = Column(String)
    size = Column(Float)
    words = Column(Integer)
    number_page = Column(Integer)
    language = Column(String)
    status = Column(String, default="unparsed")
    folder_id = Column(Integer, ForeignKey("folders.id"))
    parsed_data = Column(JSONB)

    folder = relationship("Folder", back_populates="files")

class JobDescription(Base):
    __tablename__ = "job_descriptions"  # Changed from "job_description" to "job_descriptions"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(String)
    user_id = Column(Integer, ForeignKey("users.id"))

    owner = relationship("User")

class CVInfo(Base):
    __tablename__ = "cv_info"

    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer)
    user_id = Column(Integer, ForeignKey("users.id"))
    
    # Personal Information
    full_name = Column(String)
    industry = Column(String)
    job_title = Column(String)
    level = Column(String)
    phone = Column(String)
    address = Column(String)
    city_province = Column(String)
    country = Column(String)
    date_of_birth = Column(Date)
    gender = Column(String)
    linkedin = Column(String)
    
    summary = Column(Text)
    yoe = Column(Integer)
    skills = Column(ARRAY(String))
    objectives = Column(Text)
    
    user = relationship("User", back_populates="cv_info")
    education = relationship("Education", back_populates="cv_info")
    experience = relationship("Experience", back_populates="cv_info")
    certificates = relationship("Certificate", back_populates="cv_info")
    projects = relationship("Project", back_populates="cv_info")
    awards = relationship("Award", back_populates="cv_info")

class Education(Base):
    __tablename__ = "cv_education"

    id = Column(Integer, primary_key=True, index=True)
    cv_info_id = Column(Integer, ForeignKey("cv_info.id"))
    degree = Column(String)
    institution_name = Column(String)
    major = Column(String)
    gpa = Column(String)
    start_time = Column(Date)
    end_time = Column(Date)

    cv_info = relationship("CVInfo", back_populates="education")

class Experience(Base):
    __tablename__ = "cv_experience"

    id = Column(Integer, primary_key=True, index=True)
    cv_info_id = Column(Integer, ForeignKey("cv_info.id"))
    company_name = Column(String)
    job_title = Column(String)
    working_industry = Column(String)
    level = Column(String)
    detailed_working_description = Column(ARRAY(String))
    achievements = Column(ARRAY(String))
    start_time = Column(Date)
    end_time = Column(Date)

    cv_info = relationship("CVInfo", back_populates="experience")

class Certificate(Base):
    __tablename__ = "cv_certificate"

    id = Column(Integer, primary_key=True, index=True)
    cv_info_id = Column(Integer, ForeignKey("cv_info.id"))
    type = Column(String)  # 'language' or 'other'
    language = Column(String, nullable=True)
    certificate_name = Column(String)
    certificate_point_level = Column(String)
    start_time = Column(Date)
    end_time = Column(Date)

    cv_info = relationship("CVInfo", back_populates="certificates")

    
class Project(Base):
    __tablename__ = "cv_project"

    id = Column(Integer, primary_key=True, index=True)
    cv_info_id = Column(Integer, ForeignKey("cv_info.id"))
    project_name = Column(String)
    start_time = Column(Date)
    end_time = Column(Date)
    detailed_descriptions = Column(ARRAY(String))

    cv_info = relationship("CVInfo", back_populates="projects")

class Award(Base):
    __tablename__ = "cv_award"

    id = Column(Integer, primary_key=True, index=True)
    cv_info_id = Column(Integer, ForeignKey("cv_info.id"))
    award_name = Column(String)
    time = Column(Date)
    description = Column(Text)

    cv_info = relationship("CVInfo", back_populates="awards")

class JobManagement(Base):
    __tablename__ = "manage_job"

    job_id = Column(Integer, primary_key=True, index=True)
    service_name = Column(String, nullable=False)  # Possible values: 'cv_parsing', 'cv_scoring'
    folder_name = Column(String, nullable=False)
    status = Column(Enum("parsing", "parsed_complete", "parsed_apart", name="job_status"), nullable=False)

    # Relationship examples if needed
    folder_id = Column(Integer, ForeignKey("folders.id"), nullable=True)
    folder = relationship("Folder", back_populates="jobs")
