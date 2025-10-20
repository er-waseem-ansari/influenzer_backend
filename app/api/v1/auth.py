from fastapi import APIRouter, Depends
from app.schemas.auth import TokenResponse, PhoneOTPRequest, GoogleAuthRequest, TokenRefreshRequest
from app.database import get_db
from sqlalchemy.orm import Session

from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/phone", response_model= TokenResponse)
async def phone_auth(request: PhoneOTPRequest, db: Session = Depends(get_db)):
    return await AuthService.phone_auth(
        db = db,
        firebase_id_token = request.id_token,
        role = request.role,
        device_info = request.device_info
    )

@router.post("/google", response_model=TokenResponse)
async def google_auth(request: GoogleAuthRequest, db: Session = Depends(get_db)):
    return await AuthService.google_auth(
        db=db,
        id_token_str=request.id_token,
        role=request.role,
        device_info=request.device_info
    )

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: TokenRefreshRequest, db: Session = Depends(get_db)):
    return await AuthService.refresh_access_token(db=db, refresh_token_str=request.refresh_token)
