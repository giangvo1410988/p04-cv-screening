# File: schemas.py

from pydantic import BaseModel, EmailStr
from typing import Optional
from enum import Enum
from datetime import datetime

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
        orm_mode = True

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
        orm_mode = True

class FolderWithDetails(Folder):
    num_files: int
    size: int

    class Config:
        orm_mode = True

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
        orm_mode = True

class FileUpdate(BaseModel):
    status: Optional[str] = None

    class Config:
        from_attributes = True
        orm_mode = True

class FileUploadResponse(BaseModel):
    uploaded_files: list[File]
    message: str
    duplicate_files: list[str]
    invalid_files: list[str]