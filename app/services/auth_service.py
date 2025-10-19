from typing import Optional
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy import select, or_, and_
from config import get_settings
from core.firebase import verify_firebase_token
from core.google_auth import verify_google_token
from core.security import create_access_token, create_refresh_token, decode_token
from models.token import RefreshToken
from models.user import UserRole, User, ProfileStatus

settings = get_settings()

class AuthService:
    """
        Handles all authentication logic:
        - Phone OTP authentication
        - Google OAuth authentication
        - Token refresh
        - User creation
        """

    @staticmethod
    async def phone_auth(db: Session, firebase_id_token: str, role: UserRole, device_info: str) -> dict:
        """
                Authenticate user with Firebase phone OTP.
                Creates user if it doesn't exist (hybrid approach).

                Args:
                    db: Database session
                    firebase_id_token: Firebase ID token from Flutter
                    role: User role (influencer/brand)
                    device_info: Device/platform information

                Returns:
                    dict: TokenResponse with access_token, refresh_token, etc.
                """
        # Step 1: Verify Firebase token
        firebase_data = await verify_firebase_token(firebase_id_token)
        firebase_uid = firebase_data['uid']
        phone = firebase_data.get('phone_number')  # Format: +919876543210

        if not phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone number not found in Firebase token"
            )
        # Step 2: Check if user exists - UPDATED QUERY
        user = db.execute(
            select(User).where(and_(User.firebase_uid == firebase_uid))
        ).scalar_one_or_none()

        if not user:
            # Step 3: Create new user
            user = User(
                name=firebase_data.get('name', f"User_{phone[-4:]}"),
                phone=phone,
                firebase_uid=firebase_uid,
                role=role,
                profile_status=ProfileStatus.BASIC
            )

            try:
                db.add(user)
                db.commit()
                db.refresh(user)

            except IntegrityError:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="User with this phone number already exists"
                )
        # Generate tokens
        return AuthService._generate_token_response(db, user, device_info)

    @staticmethod
    def _generate_token_response(
            db: Session,
            user: User,
            device_info: Optional[str] = None
    ) -> dict:
        """Helper method to generate access + refresh tokens"""

        # Token payload
        token_data = {
            "sub": str(user.id),
            "role": user.role.value,
            "profile_status": user.profile_status.value
        }

        # Generate tokens
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)

        # Store refresh token in DB
        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        db_refresh_token = RefreshToken(
            user_id=user.id,
            token=refresh_token,
            expires_at=expires_at,
            device_info=device_info,
            is_revoked=False
        )

        db.add(db_refresh_token)
        db.commit()

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        }

    @staticmethod
    async def google_auth(db: Session, id_token_str: str, role: UserRole, device_info: Optional[str] = None) -> dict:
        google_data = await verify_google_token(id_token_str)
        google_id = google_data['sub']
        email = google_data.get('email')
        name = google_data.get('name', 'Google User')

        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email not found in Google token"
            )
        # Check if user exists
        stmt = select(User).where(
            or_(User.google_id == google_id, User.email == email)
        )
        result = db.execute(stmt)
        user = result.scalar_one_or_none()

        if user:
            # Update google_id if missing
            if not user.google_id:
                user.google_id = google_id
                db.commit()
                db.refresh(user)

        else:
            # Create ONLY user record (NOT profile)
            user = User(
                name=name,
                email=email,
                google_id=google_id,
                role=role,
                is_verified=True,
                profile_status=ProfileStatus.BASIC  # Needs profile completion
            )
            try:
                db.add(user)
                db.commit()
                db.refresh(user)

            except IntegrityError:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="User with this email already exists"
                )
        # Generate tokens
        return AuthService._generate_token_response(db, user, device_info)

    @staticmethod
    async def refresh_access_token(
            db: Session,
            refresh_token_str: str
    ) -> dict:
        """Generate new access token using refresh token"""

        try:
            # Decode and verify token
            payload = decode_token(refresh_token_str)

            # Check token type
            if payload.get('type') != 'refresh':
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token type"
                )

            user_id = payload.get('sub')

            # Check if token exists in DB and not revoked
            stmt = select(RefreshToken).where(
                and_(
                    RefreshToken.token == refresh_token_str,
                    RefreshToken.user_id == user_id,
                    RefreshToken.is_revoked == False
                )
            )
            result = db.execute(stmt)
            db_token = result.scalar_one_or_none()

            if not db_token:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or revoked refresh token"
                )

            # Check expiration
            if db_token.expires_at < datetime.now(timezone.utc):
                db_token.is_revoked = True
                db.commit()
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Refresh token expired"
                )

            # Get user
            stmt = select(User).where(and_(User.id == user_id))
            result = db.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )

            # Generate new access token
            access_token = create_access_token({
                "sub": str(user.id),
                "role": user.role.value,
                "profile_status": user.profile_status.value
            })

            return {
                "access_token": access_token,
                "refresh_token": refresh_token_str,
                "token_type": "bearer",
                "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid refresh token: {str(e)}"
            )