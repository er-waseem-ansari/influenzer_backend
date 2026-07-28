"""Brand-facing postback integration management.

Brands create an integration to obtain a signing secret (shown once), rotate it,
and list their integrations. Writes require a write-capable brand role
(ADMIN/MANAGER), mirroring the campaign/profile routers; reads are open to any
active member. The secret is returned only by create/rotate.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.dependencies import BrandContext, get_brand_context, require_brand_editor
from app.database import get_db
from app.schemas.integration import (
    IntegrationCreate,
    IntegrationResponse,
    IntegrationSecretResponse,
)
from app.services.integration_service import IntegrationService

read_router = APIRouter(prefix="/brand/integrations", tags=["Postback Integrations"])
write_router = APIRouter(
    prefix="/brand/integrations",
    tags=["Postback Integrations"],
    dependencies=[Depends(require_brand_editor)],
)


def _secret_response(integration, secret: str) -> IntegrationSecretResponse:
    return IntegrationSecretResponse(
        integration=IntegrationResponse.model_validate(integration), secret=secret
    )


@write_router.post("", response_model=IntegrationSecretResponse, status_code=status.HTTP_201_CREATED)
async def create_integration(
    payload: IntegrationCreate,
    ctx: BrandContext = Depends(get_brand_context),
    db: Session = Depends(get_db),
):
    """Create an integration and return its signing secret (shown only once)."""
    integration, secret = IntegrationService.create(db, ctx.brand.id, payload.label)
    return _secret_response(integration, secret)


@write_router.post("/{integration_id}/rotate", response_model=IntegrationSecretResponse)
async def rotate_integration(
    integration_id: UUID,
    ctx: BrandContext = Depends(get_brand_context),
    db: Session = Depends(get_db),
):
    """Issue a fresh signing secret; the previous secret stops working immediately."""
    integration, secret = IntegrationService.rotate(db, ctx.brand.id, integration_id)
    return _secret_response(integration, secret)


@read_router.get("", response_model=list[IntegrationResponse])
async def list_integrations(
    ctx: BrandContext = Depends(get_brand_context),
    db: Session = Depends(get_db),
):
    """List the brand's integrations (no secrets)."""
    return [IntegrationResponse.model_validate(i) for i in IntegrationService.list(db, ctx.brand.id)]
