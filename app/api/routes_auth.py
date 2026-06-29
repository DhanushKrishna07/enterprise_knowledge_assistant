"""
app/api/routes_auth.py — Authentication routes: login, me.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_current_user
from app.api.schemas import LoginRequest, TokenResponse, UserResponse
from app.auth.security import create_access_token
from app.auth.service import authenticate_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest) -> Any:
    user = authenticate_user(request.email, request.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )
    token = create_access_token({"sub": user["email"]})
    return TokenResponse(
        access_token=token,
        role=user["role"],
        department=user["department"],
        email=user["email"],
    )


@router.get("/me", response_model=UserResponse)
async def me(current_user: dict = Depends(get_current_user)) -> Any:
    return UserResponse(
        id=current_user["id"],
        email=current_user["email"],
        role=current_user["role"],
        department=current_user["department"],
    )
