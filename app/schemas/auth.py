from pydantic import BaseModel, Field
from typing import Optional
from app.models.user import UserRole

class GenerateOTPRequest(BaseModel):
    phone_number: str = Field(..., alias='phoneNumber')  # E.164 format: +919876543210
    device_info: Optional[str] = Field(None, alias='deviceInfo')  # Flutter device fingerprint

class VerifyOTPRequest(BaseModel):
    phone_number: str = Field(..., alias='phoneNumber')  # Firebase token
    otp: str = Field(..., alias='otp')  # OTP code
    user_role: UserRole = Field(..., alias='userRole')  # "influencer" or "brand"
    device_info: Optional[str] = Field(None, alias='deviceInfo')

class GoogleAuthRequest(BaseModel):
    id_token: str = Field(..., alias='idToken')
    user_role: UserRole  = Field(..., alias='userRole') # "influencer" or "brand"
    device_info: Optional[str] = Field(None, alias='deviceInfo')

class TokenRefreshRequest(BaseModel):
    refresh_token: str = Field(..., alias='refreshToken')

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int