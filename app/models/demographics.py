from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey, Enum, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base

class AudienceDemographics(Base):
    __tablename__ = "audience_demographics"

    id = Column(Integer, primary_key=True, index=True)
    influencer_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    platform = Column(Enum('instagram', 'youtube', 'tiktok'), nullable=False)

    # Age distribution (percentages)
    age_0_12 = Column(Float, default=0)
    age_13_17 = Column(Float, default=0)
    age_18_24 = Column(Float, default=0)
    age_25_34 = Column(Float, default=0)
    age_35_44 = Column(Float, default=0)
    age_45_54 = Column(Float, default=0)
    age_55_plus = Column(Float, default=0)

    # Gender distribution
    gender_male = Column(Float, default=0)
    gender_female = Column(Float, default=0)
    gender_other = Column(Float, default=0)

    # Top locations (JSON array of objects)
    top_cities = Column(JSON, nullable=True)  # [{"city": "Mumbai", "percentage": 25}, ...]
    top_countries = Column(JSON, nullable=True)

    # Interests (if available from API)
    top_interests = Column(JSON, nullable=True)  # ["Technology", "Gaming", ...]

    last_updated = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    influencer = relationship("User", backref="audience_demographics")