# File: models.py

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, Enum, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
import datetime

from database import Base
from schemas import Role

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    point = Column(Integer, default=0)
    phone = Column(String, default="0981234567")
    role = Column(Enum(Role), default=Role.ENDUSER)
    is_activated = Column(Boolean, default=False)
    otp = Column(String, nullable=True)

    # Add this line to create the relationship with Folder
    folders = relationship("Folder", back_populates="owner")

class Folder(Base):
    __tablename__ = "folders"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))

    # Update this line to match the relationship in User
    owner = relationship("User", back_populates="folders")
    files = relationship("File", back_populates="folder")

class File(Base):
    __tablename__ = "files"

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

    folder = relationship("Folder", back_populates="files")


class JobDescription(Base):
    __tablename__ = "job_descriptions"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(String)
    user_id = Column(Integer, ForeignKey("users.id"))

    owner = relationship("User")