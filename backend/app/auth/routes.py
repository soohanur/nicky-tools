"""Auth routes: register (admin-key gated), login, me."""

from __future__ import annotations

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.jwt import create_access_token, get_password_hash, verify_password
from app.auth.models import User
from app.auth.schemas import Token, UserCreate, UserResponse
from app.config import get_settings
from app.core.db import get_db

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)) -> User:
    """Register a new user. Requires the admin secret key."""
    if user_data.admin_key != get_settings().ADMIN_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin key. Contact administrator for access.",
        )

    result = await db.execute(
        select(User).where((User.email == user_data.email) | (User.username == user_data.username))
    )
    existing_user = result.scalar_one_or_none()
    if existing_user:
        if existing_user.email == user_data.email:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Email already registered")
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Username already taken")

    user = User(
        email=user_data.email,
        username=user_data.username,
        full_name=user_data.full_name,
        hashed_password=get_password_hash(user_data.password),
        is_active=True,
        is_superuser=False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=Token)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Login with username or email + password. Returns a JWT."""
    result = await db.execute(
        select(User).where(
            (User.username == form_data.username) | (User.email == form_data.username)
        )
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Inactive user")

    token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(minutes=get_settings().ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
async def me(
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return user
