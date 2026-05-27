"""Create all database tables from the SQLAlchemy models.

NOTE: `create_all` only CREATES missing tables; it never ALTERs existing ones.
After a schema change (e.g. the brand_profiles columns / new brand tables /
UUID primary keys), drop the affected tables first, then re-run this script.
"""
from app.database import Base, engine

# Import every model so it registers on Base.metadata before create_all().
from app.models.user import User  # noqa: F401
from app.models.token import RefreshToken  # noqa: F401
from app.models.otp import OTPVerification  # noqa: F401
from app.models.email_verification import EmailVerificationToken  # noqa: F401
from app.models.brand import BrandProfile  # noqa: F401
from app.models.brand_members import BrandMember  # noqa: F401
from app.models.brand_social_links import BrandSocialLink  # noqa: F401
from app.models.brand_oauth_connections import BrandOAuthConnection  # noqa: F401
from app.models.brand_billing_details import BrandBillingDetail  # noqa: F401
from app.models.influencer import (  # noqa: F401
    InfluencerProfile,
    InfluencerPortfolio,
    InfluencerAnalytics,
)
from app.models.demographics import AudienceDemographics  # noqa: F401

# Create all tables
Base.metadata.create_all(bind=engine)
print("Tables created successfully!")