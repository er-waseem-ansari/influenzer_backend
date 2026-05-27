"""Reusable FastAPI dependencies for authentication and brand authorization.

`get_current_user` validates the bearer access token and loads the user.
`get_brand_context` resolves the brand the caller belongs to (read access),
and `require_brand_editor` additionally enforces a write-capable role.

All failures raise `BaseAppException` subclasses, which the global handlers
render as RFC 9457 problem responses.
"""
import uuid
from dataclasses import dataclass

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenException, NotFoundException, UnauthorizedException
from app.core.security import decode_token
from app.database import get_db
from app.models.brand import BrandProfile
from app.models.brand_members import BrandMember, BrandMemberRole
from app.models.user import User, UserRole

# auto_error=False so a missing header yields our RFC 9457 401 rather than
# Starlette's default JSON shape.
_bearer = HTTPBearer(auto_error=False)

_WRITE_ROLES = {BrandMemberRole.ADMIN, BrandMemberRole.MANAGER}


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """Authenticate the request from its `Authorization: Bearer <jwt>` header."""
    if credentials is None or not credentials.credentials:
        raise UnauthorizedException("Authentication credentials were not provided.")

    try:
        payload = decode_token(credentials.credentials)
    except JWTError:
        raise UnauthorizedException("Invalid or expired authentication token.")

    if payload.get("type") != "access":
        raise UnauthorizedException("Invalid token type for this operation.")

    try:
        user_id = uuid.UUID(str(payload.get("sub")))
    except (ValueError, TypeError):
        raise UnauthorizedException("Malformed authentication token.")

    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.is_active:
        raise UnauthorizedException("Account is inactive or no longer exists.")

    return user


def require_brand_user(user: User = Depends(get_current_user)) -> User:
    """Ensure the caller is a brand account."""
    if user.user_role != UserRole.BRAND:
        raise ForbiddenException("This resource is only available to brand accounts.")
    return user


@dataclass
class BrandContext:
    """The authenticated user together with their active brand membership."""

    user: User
    membership: BrandMember
    brand: BrandProfile

    @property
    def can_write(self) -> bool:
        return self.membership.role in _WRITE_ROLES


def get_brand_context(
    user: User = Depends(require_brand_user),
    db: Session = Depends(get_db),
) -> BrandContext:
    """Resolve the brand the caller belongs to. Grants read access to any
    active member."""
    membership = (
        db.query(BrandMember)
        .filter(BrandMember.user_id == user.id, BrandMember.is_active.is_(True))
        .order_by(BrandMember.created_at.asc())
        .first()
    )
    if membership is None:
        raise NotFoundException("No active brand is associated with this account.")

    brand = db.query(BrandProfile).filter(BrandProfile.id == membership.brand_id).first()
    if brand is None:
        raise NotFoundException("Brand profile not found.")

    return BrandContext(user=user, membership=membership, brand=brand)


def require_brand_editor(ctx: BrandContext = Depends(get_brand_context)) -> BrandContext:
    """Require a write-capable role (ADMIN or MANAGER) on the brand."""
    if not ctx.can_write:
        raise ForbiddenException("You do not have permission to modify this brand.")
    return ctx