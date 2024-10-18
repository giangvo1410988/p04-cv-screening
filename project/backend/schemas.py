# File: schemas.py

from pydantic import BaseModel, EmailStr, validator
from typing import Optional, List
from enum import Enum
from datetime import datetime, date

class Role(str, Enum):
    ADMIN = "admin"
    ENDUSER = "enduser"

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class UserBase(BaseModel):
    username: str
    email: EmailStr

class UserCreate(UserBase):
    password: str
    phone: str = "0981234567"

class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    phone: Optional[str] = None

class User(UserBase):
    id: int
    role: Role
    is_activated: bool
    point: int

    class Config:
        from_attributes = True

class OTPVerify(BaseModel):
    username: str  # Can be username or email
    otp: str

class UserStatusUpdate(BaseModel):
    is_activated: bool

class FolderBase(BaseModel):
    name: str

class FolderCreate(FolderBase):
    pass

class Folder(FolderBase):
    id: int
    user_id: int

    class Config:
        from_attributes = True

class FolderWithDetails(Folder):
    num_files: int
    size: int

    class Config:
        from_attributes = True

class FileBase(BaseModel):
    filename: str
    file_type: str
    size: float
    words: int
    number_page: int
    language: str
    status: str = "unparsed"

class FileCreate(FileBase):
    folder_id: int

class File(FileBase):
    id: int
    folder_id: int
    uploaded_date: datetime
    parsed_data: Optional[dict] = None
    class Config:
        from_attributes = True
        from_attributes = True

class FileUpdate(BaseModel):
    status: Optional[str] = None

    class Config:
        from_attributes = True
        from_attributes = True

class FileUploadResponse(BaseModel):
    uploaded_files: list[File]
    message: str
    duplicate_files: list[str]
    invalid_files: list[str]

class JobStatus(str, Enum):
    PARSING = "parsing"
    PARSED_COMPLETE = "parsed_complete"
    PARSED_APART = "parsed_apart"

class JobManagement(BaseModel):
    job_id: int
    service_name: str
    folder_name: str
    status: JobStatus
    folder_id: Optional[int] = None

    class Config:
        from_attributes = True
# Education Response Schema
class EducationResponse(BaseModel):
    id: Optional[int] = None
    degree: Optional[str] = None
    institution_name: Optional[str] = None
    major: Optional[str] = None
    gpa: Optional[str] = None
    start_time: Optional[date] = None
    end_time: Optional[date] = None

    class Config:
        from_attributes = True


# Experience Response Schema
class ExperienceResponse(BaseModel):
    id: Optional[int] = None
    company_name: Optional[str] = None
    job_title: Optional[str] = None
    working_industry: Optional[str] = None
    level: Optional[str] = None
    detailed_working_description: Optional[List[str]] = None
    achievements: Optional[List[str]] = None
    start_time: Optional[date] = None
    end_time: Optional[date] = None

    class Config:
        from_attributes = True


# Certificate Response Schema
class CertificateResponse(BaseModel):
    id: Optional[int] = None
    type: Optional[str] = None  # 'language' or 'other'
    language: Optional[str] = None
    certificate_name: Optional[str] = None
    certificate_point_level: Optional[str] = None
    start_time: Optional[date] = None
    end_time: Optional[date] = None

    class Config:
        from_attributes = True


# Project Response Schema
class ProjectResponse(BaseModel):
    id: Optional[int] = None
    project_name: Optional[str] = None
    detailed_descriptions: Optional[List[str]] = None
    start_time: Optional[date] = None
    end_time: Optional[date] = None

    class Config:
        from_attributes = True


# Award Response Schema
class AwardResponse(BaseModel):
    id: Optional[int] = None
    award_name: Optional[str] = None
    time: Optional[date] = None
    description: Optional[str] = None

    class Config:
        from_attributes = True


# CVInfo Response Schema with Related Tables
class CVInfoResponse(BaseModel):
    id: Optional[int] = None
    file_id: Optional[int] = None
    user_id: Optional[int] = None
    full_name: Optional[str] = None
    industry: Optional[str] = None
    job_title: Optional[str] = None
    level: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city_province: Optional[str] = None
    country: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    linkedin: Optional[str] = None
    summary: Optional[str] = None
    yoe: Optional[int] = None
    skills: Optional[List[str]] = None
    objectives: Optional[str] = None

    # Related tables
    education: Optional[List[EducationResponse]] = None
    experience: Optional[List[ExperienceResponse]] = None
    certificates: Optional[List[CertificateResponse]] = None
    projects: Optional[List[ProjectResponse]] = None
    awards: Optional[List[AwardResponse]] = None

    class Config:
        from_attributes = True

class JobLocation(BaseModel):
    city: Optional[str] = None
    country: Optional[str] = None

class ExperienceRequirements(BaseModel):
    yoe: Optional[int] = None

class EducationRequirements(BaseModel):
    degree: Optional[str] = None
    major: Optional[str] = None

class PointsRange(BaseModel):
    min_points: Optional[int] = None
    max_points: Optional[int] = None

class JobRequirements(BaseModel):
    skills: Optional[List[str]] = []
    languages: Optional[List[str]] = []
    experience: Optional[ExperienceRequirements] = None
    education: Optional[EducationRequirements] = None
    points: Optional[PointsRange] = None  # Added points range

class JobDescription(BaseModel):
    job_title: Optional[str] = None
    industry: Optional[str] = None
    company_name: Optional[str] = None
    location: Optional[JobLocation] = None
    employment_type: Optional[str] = None
    level: Optional[str] = None
    job_requirements: Optional[JobRequirements] = None
    salary: Optional[str] = None
    start_time: Optional[date] = None  # Keep it Optional for better validation

    @validator('start_time', pre=True, always=True)
    def check_dates(cls, value):
        if value in ["Not specified", "", None]:
            return None
        return value

    class Config:
        from_attributes = True

class CandidateCreate(BaseModel):
    job_title: str
    industry: str
    city: str
    country: str
    skills: List[str]
    degree: Optional[str] = None
    major: Optional[str] = None

    class Config:
        from_attributes = True

class HybridSearchRequest(BaseModel):
    query: str
    # embedding: List[float]
