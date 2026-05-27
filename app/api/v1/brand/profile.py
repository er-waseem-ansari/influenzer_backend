"""Brand profile management API.

All routes operate on the brand the authenticated caller belongs to ("me").

Cross-cutting concerns are attached at the router level:
  * `read_router`  — any active brand member (read access).
  * `write_router` — write-capable role (ADMIN/MANAGER) + write rate limiting,
                     enforced once by `brand_write_dependency`.

Controllers stay thin: they grab the request-cached `BrandContext` via
`Depends(get_brand_context)` (resolved once by the dependency chain) and
delegate to the service.
"""
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.dependencies import BrandContext, get_brand_context, require_brand_editor
from app.core.rate_limit import enforce_rate_limit
from app.database import get_db
from app.schemas.brand_profile import (
    BillingDetailsResponse,
    BillingDetailsUpdate,
    BrandOverviewResponse,
    BrandProfileResponse,
    BrandProfileUpdate,
    OAuthConnectionResponse,
    SocialLinkResponse,
    SocialLinkUpsert,
    SocialPlatform,
)
from app.services.brand_profile_service import BrandProfileService

settings = get_settings()


def brand_write_dependency(ctx: BrandContext = Depends(require_brand_editor)) -> BrandContext:
    """Router-level guard for all write routes: requires a write-capable role
    and applies a per-user write rate limit."""
    enforce_rate_limit(
        scope="brand_profile_write",
        identifier=str(ctx.user.id),
        limit=settings.BRAND_PROFILE_WRITE_RATE_LIMIT_MAX,
        window_seconds=settings.BRAND_PROFILE_WRITE_RATE_LIMIT_WINDOW_SECONDS,
    )
    return ctx


read_router = APIRouter(prefix="/brand/me", tags=["Brand Profile"])
write_router = APIRouter(
    prefix="/brand/me",
    tags=["Brand Profile"],
    dependencies=[Depends(brand_write_dependency)],
)


# --- Reads ------------------------------------------------------------------


@read_router.get("", response_model=BrandOverviewResponse)
async def get_brand_overview(
    ctx: BrandContext = Depends(get_brand_context), db: Session = Depends(get_db)
):
    """Full brand settings payload: profile, social links, billing, OAuth."""
    return BrandProfileService.get_overview(db, ctx.brand)


@read_router.get("/profile", response_model=BrandProfileResponse)
async def get_brand_profile(ctx: BrandContext = Depends(get_brand_context)):
    """Read the brand's core profile."""
    return BrandProfileService.get_profile(ctx.brand)


@read_router.get("/social-links", response_model=list[SocialLinkResponse])
async def list_social_links(
    ctx: BrandContext = Depends(get_brand_context), db: Session = Depends(get_db)
):
    """List the brand's social profile URLs."""
    return BrandProfileService.list_social_links(db, ctx.brand)


@read_router.get("/billing", response_model=BillingDetailsResponse | None)
async def get_billing(
    ctx: BrandContext = Depends(get_brand_context), db: Session = Depends(get_db)
):
    """Read the brand's billing details (sensitive identifiers are masked)."""
    return BrandProfileService.get_billing(db, ctx.brand)


@read_router.get("/oauth-connections", response_model=list[OAuthConnectionResponse])
async def list_oauth_connections(
    ctx: BrandContext = Depends(get_brand_context), db: Session = Depends(get_db)
):
    """List the brand's linked third-party accounts (tokens are never returned)."""
    return BrandProfileService.list_oauth_connections(db, ctx.brand)


# --- Writes (router-level: require_brand_editor + rate limit) ---------------


@write_router.patch("/profile", response_model=BrandProfileResponse)
async def update_brand_profile(
    payload: BrandProfileUpdate,
    ctx: BrandContext = Depends(get_brand_context),
    db: Session = Depends(get_db),
):
    """Partially update the brand's core profile (only provided fields change)."""
    return BrandProfileService.update_profile(db, ctx.brand, payload)


@write_router.put("/social-links/{platform}", response_model=SocialLinkResponse)
async def upsert_social_link(
    platform: SocialPlatform,
    payload: SocialLinkUpsert,
    ctx: BrandContext = Depends(get_brand_context),
    db: Session = Depends(get_db),
):
    """Set (create or replace) the brand's URL for a platform."""
    return BrandProfileService.upsert_social_link(db, ctx.brand, platform, payload)


@write_router.delete("/social-links/{platform}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_social_link(
    platform: SocialPlatform,
    ctx: BrandContext = Depends(get_brand_context),
    db: Session = Depends(get_db),
):
    """Remove the brand's URL for a platform."""
    BrandProfileService.delete_social_link(db, ctx.brand, platform)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@write_router.put("/billing", response_model=BillingDetailsResponse)
async def update_billing(
    payload: BillingDetailsUpdate,
    ctx: BrandContext = Depends(get_brand_context),
    db: Session = Depends(get_db),
):
    """Create or update the brand's billing details."""
    return BrandProfileService.update_billing(db, ctx.brand, payload)