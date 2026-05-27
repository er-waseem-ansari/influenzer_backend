from sqlalchemy import Column, String, DateTime, Enum, Boolean
from sqlalchemy.sql import func
from app.database import Base, uuid_pk
import enum


class UserRole(str, enum.Enum):
    INFLUENCER = "INFLUENCER"
    BRAND = "BRAND"
    ADMIN = "ADMIN"

class ProfileStatus(str, enum.Enum):
    BASIC = "BASIC"
    PARTIAL = "PARTIAL"
    COMPLETE = "COMPLETE"
    VERIFIED = "VERIFIED"

class User(Base):
    __tablename__ = "users"

    id = uuid_pk()
    name = Column(String(255), nullable=True)
    email = Column(String(255), unique=True, index=True, nullable=True)
    phone = Column(String(20), unique=True, index=True, nullable=True)
    password_hash = Column(String(255), nullable=True)  # Null for OAuth users
    user_role = Column(Enum(UserRole), nullable=False)  # Must specify during signup
    profile_status = Column(Enum(ProfileStatus), default=ProfileStatus.BASIC, nullable=False)

    # OAuth
    google_id = Column(String(255), unique=True, nullable=True, index=True)
    firebase_uid = Column(String(255), unique=True, nullable=True, index=True)

    # New additions
    is_active = Column(Boolean, default=True)  # For account suspension
    is_verified = Column(Boolean, default=False)  # Verification badge
    last_login = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())