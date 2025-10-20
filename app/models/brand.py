from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class BrandProfile(Base):
    __tablename__ = "brand_profiles"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    company_name = Column(String(255), nullable=False)
    website = Column(String(500), nullable=True)
    industry = Column(String(100), nullable=True)
    logo = Column(String(500), nullable=True)  # URL or path

    # Relationship
    user = relationship("User", backref="brand_profile")