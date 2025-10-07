from pydantic import BaseModel
from typing import Optional
from models.user import UserRole

class PhoneOTPRequest(BaseModel):
    id_token: str  # Firebase token
    role: UserRole  # "influencer" or "brand"
    device_info: Optional[str] = None

class GoogleAuthRequest(BaseModel):
    id_token: str  # Google token
    role: UserRole  # "influencer" or "brand"
    device_info: Optional[str] = None

class TokenRefreshRequest(BaseModel):
    refresh_token: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int