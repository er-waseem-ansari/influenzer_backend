"""Brand authentication API: signup, email verification, and login.

Throttling is a cross-cutting concern, so it never appears in a controller or a
service. Each endpoint has its own limit, so endpoints are grouped into one
`APIRouter` per policy and the limiter is attached at the router level via
`dependencies=[...]` (the same pattern as `profile.py`'s `write_router`). All
limits run against the shared Redis-backed counter (`app.core.rate_limit`).

`main.py` includes each of these routers.
"""
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.exceptions import BadRequestException, NotFoundException
from app.core.rate_limit import enforce_rate_limit, rate_limit_by_ip
from app.database import get_db
from app.schemas.auth import TokenResponse
from app.schemas.brand import (
    BrandLoginRequest,
    BrandSignupRequest,
    MessageResponse,
    ResendVerificationRequest,
)
from app.services.brand_service import BrandService

settings = get_settings()


def _frontend_url(path: str, **params: str) -> str:
    """Build a frontend redirect URL from FRONTEND_URL + path (+ query params)."""
    base = settings.FRONTEND_URL.rstrip("/")
    if not path.startswith("/"):
        path = f"/{path}"
    url = f"{base}{path}"
    if params:
        url = f"{url}?{urlencode(params)}"
    return url


def _resend_email_cooldown(payload: ResendVerificationRequest) -> None:
    """Per-email cooldown for resend, on top of the per-IP cap: stops a single
    address from being repeatedly emailed even across rotating IPs."""
    enforce_rate_limit(
        scope="resend_verification_email",
        identifier=payload.email.strip().lower(),
        limit=1,
        window_seconds=settings.RESEND_VERIFICATION_COOLDOWN_SECONDS,
    )


# --- Routers (one per rate-limit policy; limiter attached at the router) -----

signup_router = APIRouter(
    prefix="/brand",
    tags=["Brand"],
    dependencies=[
        Depends(
            rate_limit_by_ip(
                "brand_signup",
                limit=settings.BRAND_SIGNUP_RATE_LIMIT_MAX,
                window_seconds=settings.BRAND_SIGNUP_RATE_LIMIT_WINDOW_SECONDS,
            )
        )
    ],
)

login_router = APIRouter(
    prefix="/brand",
    tags=["Brand"],
    dependencies=[
        Depends(
            rate_limit_by_ip(
                "brand_login",
                limit=settings.BRAND_LOGIN_RATE_LIMIT_MAX,
                window_seconds=settings.BRAND_LOGIN_RATE_LIMIT_WINDOW_SECONDS,
            )
        )
    ],
)

verify_router = APIRouter(
    prefix="/brand",
    tags=["Brand"],
    dependencies=[
        Depends(
            rate_limit_by_ip(
                "email_verify",
                limit=settings.EMAIL_VERIFY_RATE_LIMIT_MAX,
                window_seconds=settings.EMAIL_VERIFY_RATE_LIMIT_WINDOW_SECONDS,
            )
        )
    ],
)

resend_router = APIRouter(
    prefix="/brand",
    tags=["Brand"],
    dependencies=[
        Depends(
            rate_limit_by_ip(
                "resend_verification_ip",
                limit=settings.RESEND_VERIFICATION_RATE_LIMIT_MAX,
                window_seconds=settings.RESEND_VERIFICATION_RATE_LIMIT_WINDOW_SECONDS,
            )
        ),
        Depends(_resend_email_cooldown),
    ],
)


# --- Endpoints ---------------------------------------------------------------


@signup_router.post(
    "/signup", response_model=MessageResponse, status_code=status.HTTP_200_OK
)
async def brand_signup(payload: BrandSignupRequest, db: Session = Depends(get_db)):
    """Begin brand signup. A new email creates the user, brand profile, and
    ADMIN membership and emails a verification link; an unverified existing
    account has its signup resumed (password reset + link resent). The response
    is identical in every case so it never reveals whether the email exists."""
    return BrandService.signup_brand_admin(
        db, email=payload.email, password=payload.password
    )


@login_router.post(
    "/login", response_model=TokenResponse, status_code=status.HTTP_200_OK
)
async def brand_login(payload: BrandLoginRequest, db: Session = Depends(get_db)):
    """Email + password login for brand-side users. Permitted only for accounts
    with user role BRAND that hold an active brand membership (any member role:
    ADMIN, MANAGER, or VIEWER). Returns access + refresh tokens."""
    return BrandService.login_brand(
        db,
        email=payload.email,
        password=payload.password,
        device_info=payload.device_info,
    )


@verify_router.get("/verify-email")
async def verify_email(token: str, db: Session = Depends(get_db)):
    """Verify an email via the link from the verification email, then redirect
    the browser to a frontend static page (verified on success, failed otherwise)."""
    try:
        BrandService.verify_email(db, token=token)
    except (BadRequestException, NotFoundException) as exc:
        return RedirectResponse(
            url=_frontend_url(settings.EMAIL_VERIFICATION_FAILED_PATH, reason=exc.code),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return RedirectResponse(
        url=_frontend_url(settings.EMAIL_VERIFIED_PATH),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@resend_router.post(
    "/resend-verification",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
)
async def resend_verification(payload: ResendVerificationRequest, db: Session = Depends(get_db)):
    """Re-send the verification email. Responds generically to avoid revealing
    whether an account exists for the given email."""
    return BrandService.resend_verification(db, email=payload.email)