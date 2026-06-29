"""
app/auth/security.py — JWT issuing/validation and password hashing.
"""

from __future__ import annotations

import datetime
from typing import Any

import bcrypt

if not hasattr(bcrypt, "__about__"):

    class About:
        pass

    about = About()
    about.__version__ = getattr(bcrypt, "__version__", "4.0.0")
    bcrypt.__about__ = about

# Patch bcrypt.hashpw to truncate long passwords to prevent ValueError
_orig_hashpw = bcrypt.hashpw


def _patched_hashpw(password, salt):
    if isinstance(password, str):
        password_bytes = password.encode("utf-8")
    else:
        password_bytes = password
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    # Pass to original hashpw
    return _orig_hashpw(password_bytes, salt)


bcrypt.hashpw = _patched_hashpw

from jose import jwt
from passlib.context import CryptContext

from app.core.config import get_settings

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return _pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_ctx.verify(plain, hashed)


def create_access_token(data: dict[str, Any]) -> str:
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=settings.jwt_expire_minutes)
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT. Raises JWTError on failure."""
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
