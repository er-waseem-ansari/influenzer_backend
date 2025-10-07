from pydantic import BaseModel, EmailStr, Field, field_validator
from datetime import datetime
from typing import Optional
from models.user import UserRole


class UserBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: Optional[EmailStr] = None
    phone: Optional[str] = None


class UserCreate(UserBase):
    password: Optional[str] = Field(None, min_length=8)

    @field_validator('password')
    def validate_password(self, v):
        if v is not None and len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        return v


class UserResponse(UserBase):
    id: int
    role: UserRole
    is_verified: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None