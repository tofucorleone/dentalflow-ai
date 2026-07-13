from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


UserRole = Literal["owner", "admin", "staff"]


class UserCreate(BaseModel):
    clinic_id: UUID
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=200)
    role: UserRole = "staff"
    job_title: str | None = Field(default=None, max_length=150)
    phone: str | None = Field(default=None, max_length=50)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    id: UUID
    clinic_id: UUID
    email: EmailStr
    full_name: str | None
    role: UserRole
    job_title: str | None
    phone: str | None
    active: bool
    must_change_password: bool


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
