from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
from typing import List
from schemas import Role
import models, schemas
from database import get_db
import secrets
import smtplib
from email.mime.text import MIMEText

router = APIRouter(prefix="/auth", tags=["auth"])

# JWT and password hashing setup
SECRET_KEY = "85e3eb235be45191af08db4ec8362efc6d6eded15c1d0c0bdc30c1cb36791507"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

# Email configuration
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USER = "tgiang11tn1@gmail.com"
EMAIL_PASSWORD = "xmdg ouhn oqsh psfq"

def create_access_token(data: dict, expires_delta: timedelta or None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def authenticate_user(db: Session, username: str, password: str):
    user = db.query(models.User).filter(
        (models.User.username == username) | (models.User.email == username)
    ).first()
    if not user or not user.is_activated:
        return False
    if not pwd_context.verify(password, user.hashed_password):
        return False
    return user

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = schemas.TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = db.query(models.User).filter(
        (models.User.username == token_data.username) | (models.User.email == token_data.username)
    ).first()
    if user is None or not user.is_activated:
        raise credentials_exception
    return user

def send_otp_email(email: str, otp: str):
    msg = MIMEText(f"Your OTP for account activation is: {otp}")
    msg['Subject'] = "Account Activation OTP"
    msg['From'] = EMAIL_USER
    msg['To'] = email

    with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.send_message(msg)

@router.post("/register", response_model=schemas.User)
def register_user(user: schemas.UserCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    print("==> user: ", user)
    db_user = db.query(models.User).filter(
        (models.User.username == user.username) | (models.User.email == user.email)
    ).first()
    print("==> user: ", user)

    if db_user:
        if db_user.email == user.email:
            detail = "Email already registered"
        elif db_user.username == user.username:
            detail = "Username already registered"
        else:
            detail = "Username or email already registered"
        print(f"==> Error: {detail}")
        raise HTTPException(status_code=400, detail=detail)

    hashed_password = pwd_context.hash(user.password)
    otp = secrets.token_hex(3)  # Generate a 6-character OTP
    db_user = models.User(username=user.username, email=user.email, hashed_password=hashed_password, point=0, role=Role.ENDUSER, is_activated=False, otp=otp)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    background_tasks.add_task(send_otp_email, user.email, otp)
    return db_user

@router.post("/verify-otp", response_model=schemas.User)
def verify_otp(otp_data: schemas.OTPVerify, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(
        (models.User.username == otp_data.username) | (models.User.email == otp_data.username)
    ).first()
    if not user or user.is_activated:
        raise HTTPException(status_code=400, detail="Invalid user or already activated")
    if user.otp != otp_data.otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")
    user.is_activated = True
    user.otp = None
    db.commit()
    db.refresh(user)
    return user

@router.post("/token", response_model=schemas.Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username/email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/users/me/", response_model=schemas.User)
async def read_users_me(current_user: schemas.User = Depends(get_current_user)):
    return current_user

@router.put("/users/me/", response_model=schemas.User)
async def update_user(user: schemas.UserUpdate, current_user: schemas.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.username:
        current_user.username = user.username
    if user.email:
        current_user.email = user.email
    if user.password:
        current_user.hashed_password = pwd_context.hash(user.password)
    db.commit()
    db.refresh(current_user)
    return current_user

@router.get("/users/", response_model=List[schemas.User])
async def read_users(skip: int = 0, limit: int = 100, current_user: schemas.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Not authorized to view all users")
    users = db.query(models.User).offset(skip).limit(limit).all()
    return users

@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: int, current_user: schemas.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Not authorized to delete users")
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return {"ok": True}

@router.put("/users/{user_id}/status", response_model=schemas.User)
async def update_user_status(user_id: int, is_activated: bool, current_user: schemas.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Not authorized to update user status")
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_activated = is_activated
    db.commit()
    db.refresh(user)
    return user

# Create admin account
def create_admin(db: Session):
    admin = db.query(models.User).filter(models.User.email == "giang.vo@aivision.vn").first()
    if not admin:
        hashed_password = pwd_context.hash("giang.vo@aivision.vn")
        admin = models.User(username="admin", email="giang.vo@aivision.vn", hashed_password=hashed_password, point=0, role=Role.ADMIN, is_activated=True)
        db.add(admin)
        db.commit()
        db.refresh(admin)
        print("Admin account created successfully")
    else:
        print("Admin account already exists")

# Call this function when your application starts
# For example, in your main.py file:
# from routers.auth import create_admin
# create_admin(Session())





