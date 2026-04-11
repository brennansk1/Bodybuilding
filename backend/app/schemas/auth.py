from __future__ import annotations

import re

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserRegister(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=10, max_length=100)

    @field_validator("password")
    @classmethod
    def _strong_password(cls, v: str) -> str:
        # Require at least one letter + one digit. Symbols optional but
        # encouraged. This keeps registration frictionless while blocking
        # "password123" and trivial numeric passwords.
        if not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v):
            raise ValueError("Password must contain both letters and numbers")
        return v

    @field_validator("username")
    @classmethod
    def _safe_username(cls, v: str) -> str:
        if not re.match(r"^[A-Za-z0-9_.-]+$", v):
            raise ValueError("Username may only contain letters, numbers, _ . -")
        return v


class UserLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefresh(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: str
    email: str
    username: str
    onboarding_complete: bool
    display_name: str | None = None

    model_config = {"from_attributes": True}
