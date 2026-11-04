import jwt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import User
from app.security import decode_access_token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    error = HTTPException(status_code=401, detail="Invalid or expired authentication token", headers={"WWW-Authenticate":"Bearer"})
    try:
        email = decode_access_token(token)
    except (jwt.InvalidTokenError, ValueError):
        raise error from None
    user = db.query(User).filter(User.email == email).first()
    if user is None or not user.is_active:
        raise error
    return user
