"""Brand profile management service.

Persists updates to a brand's profile, social links, billing details, and reads
OAuth connections. Operates on a `BrandProfile` already resolved/authorized by
the dependency layer. Raises `BaseAppException` subclasses; the global handlers
translate them into RFC 9457 responses.

Update methods follow PATCH semantics via `model_dump(exclude_unset=True)`:
only fields present in the request are written. `mode="json"` ensures enum
values are stored as their UPPERCASE string and `EmailStr` as plain text.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestException, ConflictException, NotFoundException
from app.models.brand import BrandProfile
from app.models.brand_billing_details import BrandBillingDetail
from app.models.brand_oauth_connections import BrandOAuthConnection
from app.models.brand_social_links import BrandSocialLink
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

LOGGER = logging.getLogger(__name__)


def _mask_secret(value: Optional[str]) -> Optional[str]:
    """Mask a sensitive identifier, revealing only the last four characters."""
    if not value:
        return None
    visible = value[-4:] if len(value) > 4 else ""
    return "••••" + visible


def _billing_response(billing: BrandBillingDetail) -> BillingDetailsResponse:
    resp = BillingDetailsResponse.model_validate(billing)
    # tax identifiers are decrypted by the ORM; never return them in the clear.
    resp.tax_id = _mask_secret(billing.tax_id)
    resp.gst_number = _mask_secret(billing.gst_number)
    return resp


class BrandProfileService:

    # --- Overview -----------------------------------------------------------

    @staticmethod
    def get_overview(db: Session, brand: BrandProfile) -> BrandOverviewResponse:
        links = (
            db.query(BrandSocialLink)
            .filter(BrandSocialLink.brand_id == brand.id)
            .order_by(BrandSocialLink.platform.asc())
            .all()
        )
        billing = (
            db.query(BrandBillingDetail)
            .filter(BrandBillingDetail.brand_id == brand.id)
            .first()
        )
        connections = (
            db.query(BrandOAuthConnection)
            .filter(BrandOAuthConnection.brand_id == brand.id)
            .order_by(BrandOAuthConnection.connected_at.asc())
            .all()
        )
        return BrandOverviewResponse(
            profile=BrandProfileResponse.model_validate(brand),
            social_links=[SocialLinkResponse.model_validate(link) for link in links],
            billing=_billing_response(billing) if billing else None,
            oauth_connections=[
                OAuthConnectionResponse.model_validate(c) for c in connections
            ],
        )

    # --- Profile ------------------------------------------------------------

    @staticmethod
    def get_profile(brand: BrandProfile) -> BrandProfileResponse:
        return BrandProfileResponse.model_validate(brand)

    @staticmethod
    def update_profile(
        db: Session, brand: BrandProfile, payload: BrandProfileUpdate
    ) -> BrandProfileResponse:
        # mode="json" -> enums become their UPPERCASE value, EmailStr -> str.
        data = payload.model_dump(mode="json", exclude_unset=True, by_alias=False)

        for field, value in data.items():
            setattr(brand, field, value)

        # Re-check the age range against the merged state (a partial update may
        # only carry one bound while the other already exists in the DB).
        if (
            brand.min_age is not None
            and brand.max_age is not None
            and brand.min_age > brand.max_age
        ):
            raise BadRequestException("minAge cannot be greater than maxAge.")

        db.commit()
        db.refresh(brand)
        LOGGER.info("Brand profile updated: brand_id=%s fields=%s", brand.id, list(data))
        return BrandProfileResponse.model_validate(brand)

    # --- Social links -------------------------------------------------------

    @staticmethod
    def list_social_links(db: Session, brand: BrandProfile) -> list[SocialLinkResponse]:
        links = (
            db.query(BrandSocialLink)
            .filter(BrandSocialLink.brand_id == brand.id)
            .order_by(BrandSocialLink.platform.asc())
            .all()
        )
        return [SocialLinkResponse.model_validate(link) for link in links]

    @staticmethod
    def upsert_social_link(
        db: Session,
        brand: BrandProfile,
        platform: SocialPlatform,
        payload: SocialLinkUpsert,
    ) -> SocialLinkResponse:
        """Create or update the brand's URL for `platform` (one per platform)."""
        link = (
            db.query(BrandSocialLink)
            .filter(
                BrandSocialLink.brand_id == brand.id,
                BrandSocialLink.platform == platform.value,
            )
            .first()
        )
        if link is None:
            link = BrandSocialLink(
                brand_id=brand.id, platform=platform.value, url=payload.url
            )
            db.add(link)
        else:
            link.url = payload.url

        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise ConflictException(
                f"A link for platform '{platform.value}' already exists."
            )
        db.refresh(link)
        LOGGER.info(
            "Brand social link upserted: brand_id=%s platform=%s", brand.id, platform.value
        )
        return SocialLinkResponse.model_validate(link)

    @staticmethod
    def delete_social_link(
        db: Session, brand: BrandProfile, platform: SocialPlatform
    ) -> None:
        link = (
            db.query(BrandSocialLink)
            .filter(
                BrandSocialLink.brand_id == brand.id,
                BrandSocialLink.platform == platform.value,
            )
            .first()
        )
        if link is None:
            raise NotFoundException(
                f"No social link found for platform '{platform.value}'."
            )
        db.delete(link)
        db.commit()
        LOGGER.info(
            "Brand social link deleted: brand_id=%s platform=%s", brand.id, platform.value
        )

    # --- Billing ------------------------------------------------------------

    @staticmethod
    def get_billing(db: Session, brand: BrandProfile) -> Optional[BillingDetailsResponse]:
        billing = (
            db.query(BrandBillingDetail)
            .filter(BrandBillingDetail.brand_id == brand.id)
            .first()
        )
        return _billing_response(billing) if billing else None

    @staticmethod
    def update_billing(
        db: Session, brand: BrandProfile, payload: BillingDetailsUpdate
    ) -> BillingDetailsResponse:
        """Create-or-update the brand's single billing record."""
        billing = (
            db.query(BrandBillingDetail)
            .filter(BrandBillingDetail.brand_id == brand.id)
            .first()
        )
        created = billing is None
        if created:
            billing = BrandBillingDetail(brand_id=brand.id)
            db.add(billing)

        data = payload.model_dump(mode="json", exclude_unset=True, by_alias=False)
        for field, value in data.items():
            setattr(billing, field, value)

        if not created:
            # touch updated_at even if all values are identical
            billing.updated_at = datetime.now(timezone.utc)

        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise ConflictException("Billing details for this brand already exist.")
        db.refresh(billing)
        LOGGER.info(
            "Brand billing %s: brand_id=%s", "created" if created else "updated", brand.id
        )
        return _billing_response(billing)

    # --- OAuth connections (read-only) --------------------------------------

    @staticmethod
    def list_oauth_connections(
        db: Session, brand: BrandProfile
    ) -> list[OAuthConnectionResponse]:
        connections = (
            db.query(BrandOAuthConnection)
            .filter(BrandOAuthConnection.brand_id == brand.id)
            .order_by(BrandOAuthConnection.connected_at.asc())
            .all()
        )
        return [OAuthConnectionResponse.model_validate(c) for c in connections]