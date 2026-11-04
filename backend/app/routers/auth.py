from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas import TokenResponse, UserLogin, UserPublic, UserRegister
from app.security import create_access_token, hash_password, verify_password
router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])

@router.post("/register", response_model=UserPublic, status_code=201)
def register(payload: UserRegister, db: Session = Depends(get_db)):
    email = payload.email.lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    user = User(email=email, full_name=payload.full_name.strip(), password_hash=hash_password(payload.password), role="farmer")
    db.add(user); db.commit(); db.refresh(user)
    return user

@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    return TokenResponse(access_token=create_access_token(user.email))

@router.get("/me", response_model=UserPublic)
def me(user: User = Depends(get_current_user)):
    return user
