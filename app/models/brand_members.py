from sqlalchemy import Column, Boolean, DateTime, UniqueConstraint, Enum as SAEnum
from sqlalchemy.sql import func
from app.database import Base, uuid_pk, uuid_fk
from enum import Enum

class BrandMemberRole(str, Enum):
    ADMIN = "ADMIN"       # The one who created/owns the brand account
    MANAGER = "MANAGER"   # Can manage campaigns, etc.
    VIEWER = "VIEWER"     # Read-only access

class BrandMember(Base):
    __tablename__ = "brand_members"

    id = uuid_pk()
    brand_id = uuid_fk("brand_profiles.id", nullable=False, index=True, ondelete="CASCADE")
    user_id = uuid_fk("users.id", nullable=False, index=True, ondelete="CASCADE")
    role = Column(SAEnum(BrandMemberRole), default=BrandMemberRole.MANAGER, nullable=False)
    is_active = Column(Boolean, default=True)  # To revoke access without deleting

    invited_by = uuid_fk("users.id", nullable=True)  # Who added them
    joined_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("brand_id", "user_id", name="uq_brand_member"),
    )