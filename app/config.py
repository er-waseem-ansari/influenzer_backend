from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # App
    APP_NAME: str = "Influenzer"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    # Database
    DATABASE_URL: str

    #Phone otp
    OTP_MAX_ATTEMPTS: int = 3

    # JWT
    SECRET_KEY: str  # Generate with: openssl rand -hex 32
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # At-rest encryption (Fernet). Generate with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    ENCRYPTION_KEY: str

    # Email verification
    FRONTEND_URL: str = "http://localhost:3000"  # Frontend base URL (redirect targets after verification)
    BACKEND_URL: str = "http://localhost:8000"   # This API's public base URL (used to build the email link)
    EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS: int = 24
    # Backend GET route the email link points at (verifies, then 302s to the frontend);
    # appended after API_V1_PREFIX.
    EMAIL_VERIFY_ENDPOINT_PATH: str = "/brand/verify-email"
    # Frontend static pages the user lands on after verification:
    EMAIL_VERIFIED_PATH: str = "/email-verified"
    EMAIL_VERIFICATION_FAILED_PATH: str = "/email-verification-failed"

    # Email delivery (Resend)
    EMAIL_ENABLED: bool = True          # If False, emails are logged instead of sent
    RESEND_API_KEY: str = ""            # Empty -> fall back to logging the email
    EMAIL_FROM: str = "onboarding@resend.dev"  # Verified sender (resend.dev works for testing)
    EMAIL_FROM_NAME: str = "Influenzer"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Rate limiting (Redis-backed; atomic fixed-window counters per identifier)
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_FAIL_OPEN: bool = True  # If Redis is unreachable, allow the request (vs. block)
    TRUST_FORWARDED_FOR: bool = True  # Read client IP from X-Forwarded-For (set only behind a trusted proxy)
    BRAND_SIGNUP_RATE_LIMIT_MAX: int = 5            # max signups
    BRAND_SIGNUP_RATE_LIMIT_WINDOW_SECONDS: int = 3600   # per IP / hour
    BRAND_LOGIN_RATE_LIMIT_MAX: int = 10            # max login attempts
    BRAND_LOGIN_RATE_LIMIT_WINDOW_SECONDS: int = 300     # per IP / 5 min
    EMAIL_VERIFY_RATE_LIMIT_MAX: int = 10           # max verify attempts
    EMAIL_VERIFY_RATE_LIMIT_WINDOW_SECONDS: int = 60     # per IP / minute
    RESEND_VERIFICATION_RATE_LIMIT_MAX: int = 5     # max resends
    RESEND_VERIFICATION_RATE_LIMIT_WINDOW_SECONDS: int = 3600  # per IP / hour
    RESEND_VERIFICATION_COOLDOWN_SECONDS: int = 60  # min gap between resends per email
    BRAND_PROFILE_WRITE_RATE_LIMIT_MAX: int = 60          # max profile/social/billing writes
    BRAND_PROFILE_WRITE_RATE_LIMIT_WINDOW_SECONDS: int = 60  # per user / minute
    CAMPAIGN_WRITE_RATE_LIMIT_MAX: int = 30               # max campaign create/draft writes
    CAMPAIGN_WRITE_RATE_LIMIT_WINDOW_SECONDS: int = 60    # per user / minute

    # --- Conversion postback (server-to-server, HMAC-signed) ---
    # Clock-skew tolerance for X-Inflz-Timestamp. A signed request whose timestamp
    # is older/newer than this is rejected (bounds the replay window).
    POSTBACK_TIMESTAMP_TOLERANCE_SECONDS: int = 300       # ±5 minutes
    # Redis-backed nonce store giving full replay immunity inside the timestamp
    # window. Degrades gracefully (fail-open on the nonce check only) if Redis is
    # down, so a Redis outage never blocks legitimate conversions.
    POSTBACK_REPLAY_PROTECTION_ENABLED: bool = True
    # Per-integration flood protection (reuses the Redis sliding-window limiter).
    POSTBACK_RATE_LIMIT_MAX: int = 600                    # max events
    POSTBACK_RATE_LIMIT_WINDOW_SECONDS: int = 60          # per integration / minute
    # Fallback click-attribution window when a campaign has no affiliate cookie
    # window configured (awareness/flat campaigns still track clicks).
    POSTBACK_DEFAULT_COOKIE_WINDOW_DAYS: int = 30

    # Firebase
    FIREBASE_CREDENTIALS_PATH: str

    # Google OAuth
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str

    # Fast2SMS
    FAST2SMS_API_KEY: str
    FAST2SMS_URL: str = "https://www.fast2sms.com/dev/bulkV2"  # Default value

    # CORS
    ALLOWED_ORIGINS: list[str] = ["*"]

    class Config:
        env_file = ".env"
        case_sensitive = True

@lru_cache()
def get_settings() -> Settings:
    return Settings()