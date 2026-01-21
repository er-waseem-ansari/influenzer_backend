from sqlalchemy import Column, Integer, String, DateTime, Enum
from sqlalchemy.sql import func
from app.database import Base
import enum


class UserRole(str, enum.Enum):
    INFLUENCER = "influencer"
    BRAND = "brand"
    ADMIN = "admin"

class ProfileStatus(str, enum.Enum):
    BASIC = "basic"
    PARTIAL = "partial"
    COMPLETE = "complete"
    VERIFIED = "verified"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=True)
    email = Column(String(255), unique=True, index=True, nullable=True)
    phone = Column(String(20), unique=True, index=True, nullable=True)
    password_hash = Column(String(255), nullable=True)  # Null for OAuth users
    user_role = Column(Enum(UserRole), nullable=False)  # Must specify during signup
    profile_status = Column(Enum(ProfileStatus), default=ProfileStatus.BASIC, nullable=False)

    # OAuth
    google_id = Column(String(255), unique=True, nullable=True, index=True)
    firebase_uid = Column(String(255), unique=True, nullable=True, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())