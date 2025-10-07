from sqlalchemy.orm import Session
from models.user import UserRole, User
from models.influencer import InfluencerProfile
from models.brand import BrandProfile
from models.token import RefreshToken
from config import get_settings
from typing import Optional
from core.firebase import verify_firebase_token
from core.security import create_access_token, create_refresh_token, decode_token
from schemas.auth import TokenResponse
from fastapi import HTTPException, status
from google.oauth2 import id_token
from google.auth.transport import requests
from datetime import datetime, timezone, timedelta

settings = get_settings()

class AuthService:

    @staticmethod
    async def phone_auth(
            db: Session,
            firebase_id_token: str,
            role: UserRole,
            device_info: Optional[str] = None
    ) -> TokenResponse:
        decoded_token = await verify_firebase_token(firebase_id_token)
        phone = decoded_token['phone_number']
        firebase_uid = decoded_token['uid']

        if not phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone number not found in token"
            )

        user = db.query(User).filter(User.phone == phone).first()

        if user:
            return await AuthService._generate_tokens(db, user, device_info)

        user = User(
            name=phone,
            phone=phone,
            firebase_uid=firebase_uid,
            role=role,
            is_verified=True
        )
        db.add(user)
        db.flush()

        if role == UserRole.INFLUENCER:
            profile = InfluencerProfile(user_id=user.id)
            db.add(profile)
        elif role == UserRole.BRAND:
            profile = BrandProfile(user_id=user.id)
            db.add(profile)

        db.commit()
        db.refresh(user)

        return await AuthService._generate_tokens(db, user, device_info)

    @staticmethod
    async def google_auth(
            db: Session,
            id_token_str: str,
            role: UserRole,
            device_info: Optional[str] = None
    ) -> TokenResponse:

        try:
            decoded_token = id_token.verify_oauth2_token(
                id_token_str,
                requests.Request(),
                settings.GOOGLE_CLIENT_ID
            )
            google_id = decoded_token['sub']
            email = decoded_token.get('email')
            name = decoded_token.get('name', email)
            user = db.query(User).filter(User.google_id == google_id).first()

            if user:
                return await AuthService._generate_tokens(db, user, device_info)

            if email:
                user = db.query(User).filter(User.email == email).first()
                if user:
                    user.google_id = google_id
                    db.commit()
                    return await AuthService._generate_tokens(db, user, device_info)
            user = User(
                name=name,
                email=email,
                google_id=google_id,
                role=role,
                is_verified=True
            )
            db.add(user)
            db.flush()

            if role == UserRole.INFLUENCER:
                profile = InfluencerProfile(user_id=user.id)
                db.add(profile)
            elif role == UserRole.BRAND:
                profile = BrandProfile(user_id=user.id)
                db.add(profile)

            db.commit()
            db.refresh(user)

            return await AuthService._generate_tokens(db, user, device_info)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Google token"
            )

    @staticmethod
    async def refresh_access_token(db: Session, refresh_token_str: str) -> TokenResponse:
        payload = decode_token(refresh_token_str)
        user_id = payload.get("sub")

        # Verify token in DB
        stored_token = db.query(RefreshToken).filter(
            RefreshToken.token == refresh_token_str,
            RefreshToken.user_id == int(user_id),
            RefreshToken.is_revoked == False
        ).first()
        if not stored_token or stored_token.expires_at < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token"
            )

        user = db.query(User).filter(User.id == int(user_id)).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        access_token = create_access_token(data={"sub": str(user.id), "role": user.role.value})

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token_str,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )

    @staticmethod
    async def _generate_tokens(db: Session, user: User, device_info: Optional[str]) -> TokenResponse:
        access_token = create_access_token(data={"sub": str(user.id), "role": user.role.value})
        refresh_token_str = create_refresh_token(data={"sub": str(user.id)})

        # Store refresh token
        refresh_token = RefreshToken(
            user_id=user.id,
            token=refresh_token_str,
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            device_info=device_info
        )
        db.add(refresh_token)
        db.commit()

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token_str,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )