from sqlalchemy import Column, String, DateTime, Boolean
from sqlalchemy.sql import func
from app.database import Base, uuid_pk, uuid_fk


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = uuid_pk()
    user_id = uuid_fk("users.id", nullable=False, ondelete="CASCADE")
    refresh_token = Column(String(500), unique=True, index=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_revoked = Column(Boolean, default=False, nullable=False)
    device_info = Column(String(500), nullable=True)  # Store device/platform info
    created_at = Column(DateTime(timezone=True), server_default=func.now())