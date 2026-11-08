from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings

_password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, stored_hash: str) -> bool:
    return _password_hash.verify(password, stored_hash)


def create_access_token(subject: str) -> str:
    settings = get_settings()
    expiry = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode({"sub": subject, "exp": expiry}, settings.secret_key, algorithm="HS256")


def decode_access_token(token: str) -> str:
    payload = jwt.decode(token, get_settings().secret_key, algorithms=["HS256"])
    subject = payload.get("sub")
    if not subject:
        raise jwt.InvalidTokenError("Missing subject")
    return str(subject)
