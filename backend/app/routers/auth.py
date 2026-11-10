from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field\nfrom sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db import get_db
from app.dependencies import get_current_user
from app.models import BuyerProfile, User, VerificationCase\nfrom app.procurement_models import LogisticsProviderProfile
from app.schemas import BuyerRegister, TokenResponse, UserLogin, UserPublic, UserRegister
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])
DatabaseSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


def _admin_emails() -> set[str]:
    return {
        item.strip().lower()
        for item in get_settings().admin_emails.split(",")
        if item.strip()
    }


def _create_user(db: Session, email: str, full_name: str, password: str, role: str) -> User:
    normalized_email = email.lower()
    if db.query(User).filter(User.email == normalized_email).first():
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    user = User(
        email=normalized_email,
        full_name=full_name.strip(),
        password_hash=hash_password(password),
        role="admin" if normalized_email in _admin_emails() else role,
        verification_status="unverified",
    )
    db.add(user)
    db.flush()
    if user.role != "admin":
        db.add(
            VerificationCase(
                subject_type="user",
                subject_id=user.id,
                submitted_by_user_id=user.id,
                status="pending",
            )
        )
    return user


@router.post("/register", response_model=UserPublic, status_code=201)
def register(payload: UserRegister, db: DatabaseSession):
    user = _create_user(db, str(payload.email), payload.full_name, payload.password, "farmer")
    db.commit()
    db.refresh(user)
    return user


@router.post("/register/buyer", response_model=UserPublic, status_code=201)
def register_buyer(payload: BuyerRegister, db: DatabaseSession):
    user = _create_user(db, str(payload.email), payload.full_name, payload.password, "buyer")
    if user.role != "admin":
        db.add(
            BuyerProfile(
                user_id=user.id,
                organization_name=payload.organization_name.strip(),
                buyer_type=payload.buyer_type.strip().lower(),
                phone=payload.phone.strip(),
                location=payload.location.strip(),
            )
        )
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, db: DatabaseSession):
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if (
        user is None
        or not user.is_active
        or not verify_password(payload.password, user.password_hash)
    ):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    if user.email in _admin_emails() and user.role != "admin":
        user.role = "admin"
        db.commit()
    return TokenResponse(access_token=create_access_token(user.email))


@router.get("/me", response_model=UserPublic)
def me(user: CurrentUser):
    return user


class LogisticsProviderRegister(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=10, max_length=128)
    organization_name: str = Field(min_length=2, max_length=180)
    phone: str = Field(min_length=7, max_length=30)
    service_areas: list[str] = Field(min_length=1, max_length=30)
    transport_modes: list[str] = Field(min_length=1, max_length=10)


@router.post("/register/logistics-provider", response_model=UserPublic, status_code=201)
def register_logistics_provider(payload: LogisticsProviderRegister, db: DatabaseSession):
    user = _create_user(
        db, payload.email, payload.full_name, payload.password, "logistics_provider"
    )
    if user.role != "admin":
        db.add(LogisticsProviderProfile(
            user_id=user.id,
            organization_name=payload.organization_name.strip(),
            phone=payload.phone.strip(),
            service_areas=[area.strip() for area in payload.service_areas if area.strip()],
            transport_modes=[mode.strip().lower() for mode in payload.transport_modes if mode.strip()],
        ))
    db.commit()
    db.refresh(user)
    return user
