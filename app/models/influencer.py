from sqlalchemy import Column, Integer, String, JSON, Text, Float, DateTime, Boolean, Enum, Numeric, Date, \
    UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base, uuid_pk, uuid_fk


class InfluencerProfile(Base):
    __tablename__ = "influencer_profiles"

    user_id = uuid_fk("users.id", primary_key=True, ondelete="CASCADE")

    # Basic Info (what you have)
    bio = Column(Text, nullable=True)
    main_occupation = Column(String(255), nullable=True)  # "Tech Reviewer", "Fashion Blogger"
    niches = Column(JSON, nullable=True)  # ["Tech", "Gaming", "Lifestyle"]
    profile_pic = Column(String(500), nullable=True)
    location_city = Column(String(100), nullable=True)
    location_state = Column(String(100), nullable=True)
    location_country = Column(String(100), nullable=True)

    # Languages
    languages = Column(JSON, nullable=True)  # ["English", "Hindi", "Tamil"]

    # Social Media Connections (EXPANDED)
    instagram_username = Column(String(100), nullable=True)
    instagram_connected = Column(Boolean, default=False)
    instagram_access_token = Column(Text, nullable=True)  # For API access
    instagram_token_expires = Column(DateTime(timezone=True), nullable=True)

    youtube_channel_id = Column(String(100), nullable=True)
    youtube_connected = Column(Boolean, default=False)
    youtube_access_token = Column(Text, nullable=True)
    youtube_token_expires = Column(DateTime(timezone=True), nullable=True)

    # Other platforms (optional)
    tiktok_username = Column(String(100), nullable=True)
    twitter_username = Column(String(100), nullable=True)
    linkedin_url = Column(String(255), nullable=True)

    # Social Media Stats (Core metrics for profile display)
    instagram_followers = Column(Integer, default=0)
    instagram_avg_likes = Column(Integer, default=0)
    instagram_avg_views = Column(Integer, default=0)  # For reels

    youtube_subscribers = Column(Integer, default=0)
    youtube_avg_views = Column(Integer, default=0)
    youtube_avg_likes = Column(Integer, default=0)

    # Calculated metrics
    overall_engagement_rate = Column(Float, default=0.0)  # Calculated average
    total_reach = Column(Integer, default=0)  # Sum of all followers

    # Pricing (for your hybrid model)
    instagram_post_rate = Column(Numeric(10, 2), nullable=True)
    instagram_reel_rate = Column(Numeric(10, 2), nullable=True)
    instagram_story_rate = Column(Numeric(10, 2), nullable=True)
    youtube_integration_rate = Column(Numeric(10, 2), nullable=True)
    youtube_dedicated_rate = Column(Numeric(10, 2), nullable=True)
    custom_pricing_note = Column(Text, nullable=True)  # "Negotiable for long-term"

    # Availability
    availability_status = Column(Enum('available', 'busy', 'booked', name='influencer_availability_status'), default='available')
    next_available_date = Column(Date, nullable=True)

    # Performance Stats (for dashboard & profile)
    total_campaigns_completed = Column(Integer, default=0)
    total_campaigns_applied = Column(Integer, default=0)
    success_rate = Column(Float, default=0.0)  # applications accepted / total applied
    average_rating = Column(Float, default=0.0)
    total_reviews = Column(Integer, default=0)
    response_rate = Column(Float, default=100.0)  # % of messages responded to

    # Earnings tracking
    total_earned = Column(Numeric(12, 2), default=0)
    pending_earnings = Column(Numeric(12, 2), default=0)

    # Profile completeness
    profile_completion_percentage = Column(Integer, default=0)  # 0-100

    # Analytics last updated (for caching)
    analytics_last_synced = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", backref="influencer_profile")


class InfluencerPortfolio(Base):
    __tablename__ = "influencer_portfolios"

    id = uuid_pk()
    influencer_id = uuid_fk("users.id", nullable=False, ondelete="CASCADE")

    # Video details
    video_url = Column(String(500), nullable=False)  # S3/cloud storage URL
    thumbnail_url = Column(String(500), nullable=True)
    video_type = Column(Enum('intro', 'sample_work', 'behind_scenes', name='portfolio_video_type'), nullable=False)

    title = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    duration_seconds = Column(Integer, nullable=True)

    # Categorization
    niche_tags = Column(JSON, nullable=True)  # ["Tech", "Unboxing"]

    # If it's past work
    brand_name = Column(String(255), nullable=True)  # Can be null for intro videos
    campaign_results = Column(Text, nullable=True)  # "50K views, 7% engagement"

    # Metadata
    file_size_mb = Column(Float, nullable=True)
    is_featured = Column(Boolean, default=False)  # Pin to top
    display_order = Column(Integer, default=0)  # For sorting

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationship
    influencer = relationship("User", backref="portfolio_videos")

class InfluencerAnalytics(Base):
    __tablename__ = "influencer_analytics"

    id = uuid_pk()
    influencer_id = uuid_fk("users.id", nullable=False, ondelete="CASCADE")

    # Snapshot date
    snapshot_date = Column(Date, nullable=False, index=True)

    # Platform-wise snapshots
    instagram_followers = Column(Integer, nullable=True)
    instagram_engagement_rate = Column(Float, nullable=True)
    instagram_avg_reach = Column(Integer, nullable=True)

    youtube_subscribers = Column(Integer, nullable=True)
    youtube_avg_views = Column(Integer, nullable=True)
    youtube_watch_time_hours = Column(Float, nullable=True)

    # Aggregate metrics
    total_reach = Column(Integer, nullable=True)
    overall_engagement_rate = Column(Float, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Composite unique constraint (one snapshot per influencer per day)
    __table_args__ = (
        UniqueConstraint('influencer_id', 'snapshot_date', name='unique_daily_snapshot'),
    )

    # Relationship
    influencer = relationship("User", backref="analytics_history")