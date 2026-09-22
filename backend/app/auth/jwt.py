"""Token encode/decode + password hashing helpers."""

from __future__ import annotations

from datetime import datetime, timedelta

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    return _pwd.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _pwd.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Encode ``data`` (typically ``{"sub": user_id}``) into a signed JWT."""
    s = get_settings()
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=s.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, s.SECRET_KEY, algorithm=s.ALGORITHM)


def decode_access_token(token: str) -> str | None:
    """Return the user id from a valid token, or None."""
    s = get_settings()
    try:
        payload = jwt.decode(token, s.SECRET_KEY, algorithms=[s.ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None
