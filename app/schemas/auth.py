from pydantic import BaseModel
from typing import Optional
from app.models.user import UserRole

class GenerateOTPRequest(BaseModel):
    phone_number: str  # E.164 format: +919876543210
    device_id: Optional[str] = None  # Flutter device fingerprint

class VerifyOTPRequest(BaseModel):
    phone_number: str  # Firebase token
    otp: str  # OTP code
    role: UserRole  # "influencer" or "brand"
    device_id: Optional[str] = None

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