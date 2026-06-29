"""
app/api/dependencies.py — FastAPI dependency injection for authentication.
"""

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.auth.security import decode_access_token
from app.auth.service import get_user_by_email
from app.core.errors import UnauthorizedError

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict[str, Any]:
    """Decode JWT and return the current user dict. Raises 401 if invalid."""
    try:
        payload = decode_access_token(token)
        email: str = payload.get("sub", "")
        if not email:
            raise UnauthorizedError("Invalid token payload.")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")
    return user


async def require_admin(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """Raise 403 if the current user is not an admin."""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required.")
    return current_user
