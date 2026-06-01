"""Brand onboarding service.

Handles first-time brand signup (the signer becomes the brand ADMIN) and the
email-verification lifecycle. Services raise `BaseAppException` subclasses;
the global exception handlers translate them into RFC 9457 responses.
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.exceptions import (
    BadRequestException,
    ForbiddenException,
    NotFoundException,
    UnauthorizedException,
)
from app.core.security import (
    generate_url_safe_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models.brand import BrandProfile
from app.models.brand_members import BrandMember, BrandMemberRole
from app.models.email_verification import EmailVerificationToken
from app.models.token import RefreshToken
from app.models.user import ProfileStatus, User, UserRole
from app.schemas.auth import TokenResponse
from app.schemas.brand import MessageResponse
from app.services.auth_service import AuthService
from app.services.email_service import EmailService

LOGGER = logging.getLogger(__name__)
settings = get_settings()

# A valid bcrypt hash we verify against when the email is unknown, so login
# response time doesn't reveal whether an account exists (timing enumeration).
# The plaintext is irrelevant; it is never compared for a real match.
_DUMMY_PASSWORD_HASH = hash_password("brand-login-timing-placeholder")

# Identical signup response for every case (new / unverified / already-exists),
# so the endpoint never reveals whether an email is registered.
_SIGNUP_MESSAGE = "Verification email sent. Please check your inbox."


class BrandService:

    @staticmethod
    def _verification_expiry() -> datetime:
        return datetime.now(timezone.utc) + timedelta(
            hours=settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS
        )

    @staticmethod
    def login_brand(
        db: Session,
        *,
        email: str,
        password: str,
        device_info: str | None = None,
    ) -> TokenResponse:
        """Authenticate a brand-side user by email + password.

        Only accounts with `user_role == BRAND` that hold an *active* brand
        membership may log in here, and every member role is allowed (ADMIN,
        MANAGER, VIEWER). Returns an access + refresh token pair on success;
        token minting is delegated to the shared `AuthService` helper.

        Unknown email, wrong password, and non-brand accounts all return the
        same generic 401 to avoid account enumeration. Post-authentication
        state (deactivated, unverified, no brand) returns a specific 403 — by
        then the caller has already proven they own the account.

        Rate limiting is applied at the router (see `brand_auth.py`), keeping
        this method a pure domain operation.
        """
        normalized_email = email.strip().lower()
        invalid_credentials = UnauthorizedException("Invalid email or password.")

        user = (
            db.query(User)
            .filter(func.lower(User.email) == normalized_email)
            .first()
        )

        # Always run one bcrypt comparison (against a dummy hash when the user
        # is absent) so timing doesn't reveal whether the email exists.
        stored_hash = (
            user.password_hash if user and user.password_hash else _DUMMY_PASSWORD_HASH
        )
        password_ok = verify_password(password, stored_hash)
        if user is None or not user.password_hash or not password_ok:
            raise invalid_credentials
        # This endpoint serves brand-side accounts only.
        if user.user_role != UserRole.BRAND:
            raise invalid_credentials

        if not user.is_active:
            raise ForbiddenException(
                "This account has been deactivated. Please contact support.",
                code="ACCOUNT_DEACTIVATED",
            )
        if not user.is_verified:
            raise ForbiddenException(
                "Please verify your email address before logging in.",
                code="EMAIL_NOT_VERIFIED",
            )

        # Any active membership grants access, regardless of role.
        membership = (
            db.query(BrandMember)
            .filter(
                BrandMember.user_id == user.id,
                BrandMember.is_active.is_(True),
            )
            .first()
        )
        if membership is None:
            raise ForbiddenException(
                "Your account is not linked to an active brand.",
                code="NO_ACTIVE_BRAND",
            )

        user.last_login = datetime.now(timezone.utc)
        LOGGER.info(
            "Brand user logged in: user_id=%s brand_id=%s role=%s",
            user.id, membership.brand_id, membership.role.value,
        )
        # _generate_token_response commits, persisting last_login in the same txn.
        return AuthService._generate_token_response(db, user, device_info)

    @staticmethod
    def signout_brand(
        db: Session,
        *,
        user: User,
        refresh_token: str | None,
        all_devices: bool,
    ) -> MessageResponse:
        """Revoke refresh tokens for an authenticated brand user.

        When `all_devices` is true, every active refresh token owned by the
        caller is revoked (sign out everywhere). Otherwise `refresh_token` is
        required and only that single session is revoked. The token must
        belong to the caller — refusing other-user tokens prevents a stolen
        access token from being used to revoke an unrelated session.

        Already-revoked, unknown, or expired tokens succeed silently so a
        retried signout is idempotent and does not leak which tokens exist.
        """
        if all_devices:
            revoked = (
                db.query(RefreshToken)
                .filter(
                    RefreshToken.user_id == user.id,
                    RefreshToken.is_revoked.is_(False),
                )
                .update(
                    {RefreshToken.is_revoked: True},
                    synchronize_session=False,
                )
            )
            db.commit()
            LOGGER.info(
                "Brand user signed out from all devices: user_id=%s revoked=%s",
                user.id, revoked,
            )
            return MessageResponse(message="Signed out from all devices.")

        if not refresh_token:
            raise BadRequestException(
                "refresh_token is required unless all_devices is true."
            )

        token_row = (
            db.query(RefreshToken)
            .filter(
                RefreshToken.refresh_token == refresh_token,
                RefreshToken.user_id == user.id,
            )
            .first()
        )
        if token_row is not None and not token_row.is_revoked:
            token_row.is_revoked = True
            db.commit()
            LOGGER.info("Brand user signed out: user_id=%s", user.id)

        return MessageResponse(message="Signed out.")

    @staticmethod
    def signup_brand_admin(
        db: Session, *, email: str, password: str
    ) -> MessageResponse:
        """Begin (or resume) brand signup.

        Always returns the same neutral response so the endpoint never reveals
        whether the email is already registered (account enumeration). Three
        branches, one outcome:

          * new email                  -> create the user, brand profile, and
                                          ADMIN membership; send a verification
                                          link.
          * existing UNVERIFIED brand  -> the account is still unclaimed, so
                                          overwrite its password, re-issue the
                                          token, and resend the link.
          * any other existing account -> change nothing; send an "account
                                          already exists" notice instead.

        Overwriting the unverified account's password is deliberate and the
        secure choice: an unverified account is unclaimed, so the latest
        signer's password must win. Because the verification link only reaches
        the inbox owner, this defeats a pre-registration takeover (attacker
        registers the victim's email first, then the victim unwittingly
        verifies into the attacker's password).
        """
        normalized_email = email.strip().lower()
        existing = (
            db.query(User)
            .filter(func.lower(User.email) == normalized_email)
            .first()
        )

        if existing is not None:
            if existing.user_role == UserRole.BRAND and not existing.is_verified:
                BrandService._restart_unverified_signup(db, existing, password)
            else:
                # Verified brand, or an email owned by another account type:
                # leave it untouched and nudge the owner to log in. The throwaway
                # hash keeps this branch's timing close to the others (which all
                # run one bcrypt), so response time doesn't betray the branch.
                hash_password(password)
                EmailService.send_account_exists_email(to_email=normalized_email)
            return MessageResponse(message=_SIGNUP_MESSAGE)

        # Brand-new email: atomically create user + brand profile + ADMIN member.
        raw_token = generate_url_safe_token()
        try:
            user = User(
                email=normalized_email,
                password_hash=hash_password(password),
                user_role=UserRole.BRAND,
                profile_status=ProfileStatus.BASIC,
                is_active=True,
                is_verified=False,
            )
            db.add(user)
            db.flush()  # populate user.id without committing

            brand_profile = BrandProfile(created_by=user.id)
            db.add(brand_profile)
            db.flush()  # populate brand_profile.id

            new_user_id = user.id
            new_brand_id = brand_profile.id

            db.add(
                BrandMember(
                    brand_id=new_brand_id,
                    user_id=new_user_id,
                    role=BrandMemberRole.ADMIN,  # first signer owns the brand
                    is_active=True,
                    joined_at=datetime.now(timezone.utc),
                )
            )

            db.add(
                EmailVerificationToken(
                    user_id=new_user_id,
                    token_hash=hash_token(raw_token),
                    expires_at=BrandService._verification_expiry(),
                )
            )

            db.commit()
        except IntegrityError:
            db.rollback()
            # Lost a race with a concurrent signup on the same email; the winner
            # already sent the verification link. Stay neutral.
            return MessageResponse(message=_SIGNUP_MESSAGE)

        LOGGER.info(
            "Brand admin signed up: user_id=%s brand_id=%s", new_user_id, new_brand_id
        )
        # Side effect only after the records are durably committed.
        EmailService.send_verification_email(to_email=normalized_email, token=raw_token)
        return MessageResponse(message=_SIGNUP_MESSAGE)

    @staticmethod
    def _restart_unverified_signup(db: Session, user: User, password: str) -> None:
        """Resume signup for an unverified brand account: overwrite the password
        (the account is unclaimed until verified), invalidate any outstanding
        verification tokens, issue a fresh one, and resend the link."""
        user.password_hash = hash_password(password)
        db.query(EmailVerificationToken).filter(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.used_at.is_(None),
        ).update(
            {EmailVerificationToken.used_at: datetime.now(timezone.utc)},
            synchronize_session=False,
        )
        raw_token = generate_url_safe_token()
        db.add(
            EmailVerificationToken(
                user_id=user.id,
                token_hash=hash_token(raw_token),
                expires_at=BrandService._verification_expiry(),
            )
        )
        db.commit()
        EmailService.send_verification_email(to_email=user.email, token=raw_token)
        LOGGER.info("Resumed unverified brand signup: user_id=%s", user.id)

    @staticmethod
    def verify_email(db: Session, *, token: str) -> MessageResponse:
        """Consume an email-verification token and mark the user verified."""
        record = (
            db.query(EmailVerificationToken)
            .filter(EmailVerificationToken.token_hash == hash_token(token))
            .first()
        )

        # Same response whether the token is unknown or already consumed.
        if record is None or record.used_at is not None:
            raise BadRequestException("Invalid or already-used verification token.")

        expires_at = record.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            raise BadRequestException(
                "Verification token has expired. Please request a new one."
            )

        user = db.query(User).filter(User.id == record.user_id).first()
        if user is None:
            raise NotFoundException("User account not found.")

        record.used_at = datetime.now(timezone.utc)
        if not user.is_verified:
            user.is_verified = True
        db.commit()

        LOGGER.info("Email verified: user_id=%s", user.id)
        return MessageResponse(
            message="Email verified successfully. You can now log in."
        )

    @staticmethod
    def resend_verification(db: Session, *, email: str) -> MessageResponse:
        """Re-issue a verification email.

        Always succeeds from the caller's perspective to avoid leaking which
        emails are registered (account enumeration). Work is done only when an
        unverified brand account actually exists for the email.

        Throttling (per-IP cap + per-email cooldown) is enforced at the router
        (see `brand_auth.py`).
        """
        normalized_email = email.strip().lower()

        generic_response = MessageResponse(
            message=(
                "If an unverified account exists for that email, a new "
                "verification link has been sent."
            )
        )

        user = (
            db.query(User)
            .filter(
                func.lower(User.email) == normalized_email,
                User.user_role == UserRole.BRAND,
            )
            .first()
        )

        if user is None or user.is_verified:
            return generic_response

        # Invalidate any outstanding tokens, then issue a fresh one.
        db.query(EmailVerificationToken).filter(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.used_at.is_(None),
        ).update(
            {EmailVerificationToken.used_at: datetime.now(timezone.utc)},
            synchronize_session=False,
        )

        raw_token = generate_url_safe_token()
        db.add(
            EmailVerificationToken(
                user_id=user.id,
                token_hash=hash_token(raw_token),
                expires_at=BrandService._verification_expiry(),
            )
        )
        db.commit()

        EmailService.send_verification_email(to_email=normalized_email, token=raw_token)
        LOGGER.info("Verification email re-sent: user_id=%s", user.id)
        return generic_response