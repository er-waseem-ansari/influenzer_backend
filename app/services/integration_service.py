"""Create / rotate / read postback integrations for a brand.

The signing secret is generated here (32 random bytes, hex), returned to the
caller **once**, and persisted only via the ``EncryptedString`` column (encrypted
at rest). Rotation issues a fresh secret and stamps ``rotated_at``; the old secret
stops working immediately because only the new ciphertext remains.
"""
from __future__ import annotations

import logging
import secrets
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundException
from app.models.integration import IntegrationStatus, PostbackIntegration

LOGGER = logging.getLogger(__name__)

_PUBLIC_ID_PREFIX = "intg_"


def _new_public_id() -> str:
    """Opaque, non-enumerable handle. Carries no brand info."""
    return f"{_PUBLIC_ID_PREFIX}{secrets.token_hex(12)}"


def _new_secret() -> str:
    """High-entropy signing secret (32 bytes hex)."""
    return secrets.token_hex(32)


class IntegrationService:

    @staticmethod
    def create(db: Session, brand_id: UUID, label: str | None) -> tuple[PostbackIntegration, str]:
        """Create an integration; return ``(integration, plaintext_secret)``."""
        secret = _new_secret()
        integration = PostbackIntegration(
            public_id=_new_public_id(),
            brand_id=brand_id,
            secret=secret,
            status=IntegrationStatus.ACTIVE,
            label=label,
        )
        db.add(integration)
        db.commit()
        db.refresh(integration)
        LOGGER.info("Postback integration created: id=%s brand_id=%s", integration.id, brand_id)
        return integration, secret

    @staticmethod
    def rotate(db: Session, brand_id: UUID, integration_id: UUID) -> tuple[PostbackIntegration, str]:
        """Issue a fresh secret for the brand's integration; old one stops working."""
        from sqlalchemy.sql import func

        integration = IntegrationService._owned(db, brand_id, integration_id)
        secret = _new_secret()
        integration.secret = secret
        integration.rotated_at = func.now()
        db.commit()
        db.refresh(integration)
        LOGGER.info("Postback integration rotated: id=%s brand_id=%s", integration.id, brand_id)
        return integration, secret

    @staticmethod
    def list(db: Session, brand_id: UUID) -> list[PostbackIntegration]:
        return (
            db.query(PostbackIntegration)
            .filter(PostbackIntegration.brand_id == brand_id)
            .order_by(PostbackIntegration.created_at.desc())
            .all()
        )

    @staticmethod
    def _owned(db: Session, brand_id: UUID, integration_id: UUID) -> PostbackIntegration:
        integration = (
            db.query(PostbackIntegration)
            .filter(
                PostbackIntegration.id == integration_id,
                PostbackIntegration.brand_id == brand_id,
            )
            .first()
        )
        if integration is None:
            raise NotFoundException("Integration not found.")
        return integration
