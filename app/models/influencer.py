from sqlalchemy import Column, Integer, String, JSON, ForeignKey, Text, Float
from sqlalchemy.orm import relationship
from app.database import Base


class InfluencerProfile(Base):
    __tablename__ = "influencer_profiles"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    bio = Column(Text, nullable=True)
    niches = Column(JSON, nullable=True)  # ["Fashion", "Lifestyle"]
    social_links = Column(JSON, nullable=True)  # {"instagram": "url", "youtube": "url"}
    follower_count = Column(Integer, nullable=True)
    engagement_rate = Column(Float, nullable=True)
    demographics = Column(JSON, nullable=True)  # {"age": "18-24", "location": "India"}
    profile_pic = Column(String(500), nullable=True)  # URL or path

    # Relationship
    user = relationship("User", backref="influencer_profile")