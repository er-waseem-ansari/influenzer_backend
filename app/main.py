import uvicorn
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from app.api.v1 import collect
from app.api.v1.brand import brand_auth, campaigns, integrations, profile
from app.api.v1.influencer import auth
from app.config import get_settings
from app.core.exception_handlers import register_exception_handlers

settings = get_settings()
app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    version="1.0.0"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global exception handlers (RFC 9457 Problem Details)
register_exception_handlers(app)

# Include routers
app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(brand_auth.signup_router, prefix=settings.API_V1_PREFIX)
app.include_router(brand_auth.login_router, prefix=settings.API_V1_PREFIX)
app.include_router(brand_auth.verify_router, prefix=settings.API_V1_PREFIX)
app.include_router(brand_auth.resend_router, prefix=settings.API_V1_PREFIX)
app.include_router(brand_auth.signout_router, prefix=settings.API_V1_PREFIX)
app.include_router(profile.read_router, prefix=settings.API_V1_PREFIX)
app.include_router(profile.write_router, prefix=settings.API_V1_PREFIX)
app.include_router(campaigns.read_router, prefix=settings.API_V1_PREFIX)
app.include_router(campaigns.write_router, prefix=settings.API_V1_PREFIX)
app.include_router(integrations.read_router, prefix=settings.API_V1_PREFIX)
app.include_router(integrations.write_router, prefix=settings.API_V1_PREFIX)
# Public postback receiver: own path (no /api/v1 prefix), HMAC-authenticated.
app.include_router(collect.router)

# Health check endpoint
@app.get("/")
async def root():
    return {
        "message": f"Welcome to {settings.APP_NAME} API",
        "status": "active",
        "version": "1.0.0"
    }

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)