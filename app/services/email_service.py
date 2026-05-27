"""Email delivery via Resend.

`send_verification_email` builds the verification message (HTML + plain-text
fallback) and hands it to `_deliver`, which sends it through Resend.

Delivery is best-effort: it is called as a post-commit side effect of signup,
so a provider error is logged but never propagated (the account already exists
and the user can request a fresh link via "resend verification"). When
`EMAIL_ENABLED` is False or `RESEND_API_KEY` is unset, the message is logged
instead of sent, which keeps local development working without a key.
"""
import logging
from html import escape
from urllib.parse import urlencode

import resend

from app.config import get_settings

LOGGER = logging.getLogger(__name__)
settings = get_settings()


class EmailService:

    @staticmethod
    def build_verification_link(token: str) -> str:
        """Build the backend URL the user clicks. That endpoint verifies the
        token and then redirects the browser to a frontend static page."""
        base = settings.BACKEND_URL.rstrip("/")
        prefix = settings.API_V1_PREFIX.rstrip("/")
        path = settings.EMAIL_VERIFY_ENDPOINT_PATH
        if not path.startswith("/"):
            path = f"/{path}"
        return f"{base}{prefix}{path}?{urlencode({'token': token})}"

    @staticmethod
    def send_verification_email(*, to_email: str, token: str) -> None:
        """Send the email-verification message."""
        link = EmailService.build_verification_link(token)
        hours = settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS
        subject = "Verify your email address"

        text = (
            "Welcome to Influenzer!\n\n"
            "Please confirm your email address to activate your brand account.\n\n"
            f"Verification link (valid for {hours} hours):\n{link}\n\n"
            "If you didn't create this account, you can safely ignore this email."
        )
        safe_link = escape(link, quote=True)
        html = f"""\
<!doctype html>
<html>
  <body style="margin:0;padding:0;background:#f4f4f7;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="padding:32px 0;">
      <tr>
        <td align="center">
          <table role="presentation" width="480" cellpadding="0" cellspacing="0"
                 style="background:#ffffff;border-radius:12px;padding:40px;text-align:left;">
            <tr><td>
              <h1 style="margin:0 0 16px;font-size:22px;color:#111;">Welcome to Influenzer</h1>
              <p style="margin:0 0 24px;font-size:15px;line-height:22px;color:#444;">
                Please confirm your email address to activate your brand account.
              </p>
              <a href="{safe_link}"
                 style="display:inline-block;background:#4f46e5;color:#ffffff;text-decoration:none;
                        padding:12px 24px;border-radius:8px;font-size:15px;font-weight:600;">
                Verify email
              </a>
              <p style="margin:24px 0 8px;font-size:13px;color:#777;">
                This link is valid for {hours} hours. If the button doesn't work, paste this URL into your browser:
              </p>
              <p style="margin:0 0 24px;font-size:13px;color:#4f46e5;word-break:break-all;">{safe_link}</p>
              <p style="margin:0;font-size:12px;color:#999;">
                If you didn't create this account, you can safely ignore this email.
              </p>
            </td></tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""

        EmailService._deliver(to_email=to_email, subject=subject, html=html, text=text)

    @staticmethod
    def send_account_exists_email(*, to_email: str) -> None:
        """Tell an address that an account already exists, nudging the owner to
        log in. Sent *in place of* a verification link when someone tries to
        sign up with an email that's already registered, so the signup endpoint
        can return an identical response in every case (no account enumeration).
        Only the inbox owner ever sees which email arrived."""
        login_url = settings.FRONTEND_URL.rstrip("/")
        subject = "You already have an Influenzer account"

        text = (
            "Someone (hopefully you) tried to sign up for Influenzer with this "
            "email address, but an account already exists.\n\n"
            f"You can log in here:\n{login_url}\n\n"
            "Forgot your password? Use the 'Forgot password' option on the login "
            "page. If this wasn't you, you can safely ignore this email."
        )
        safe_url = escape(login_url, quote=True)
        html = f"""\
<!doctype html>
<html>
  <body style="margin:0;padding:0;background:#f4f4f7;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="padding:32px 0;">
      <tr>
        <td align="center">
          <table role="presentation" width="480" cellpadding="0" cellspacing="0"
                 style="background:#ffffff;border-radius:12px;padding:40px;text-align:left;">
            <tr><td>
              <h1 style="margin:0 0 16px;font-size:22px;color:#111;">You already have an account</h1>
              <p style="margin:0 0 24px;font-size:15px;line-height:22px;color:#444;">
                Someone tried to sign up for Influenzer with this email address, but
                an account already exists. Just log in instead.
              </p>
              <a href="{safe_url}"
                 style="display:inline-block;background:#4f46e5;color:#ffffff;text-decoration:none;
                        padding:12px 24px;border-radius:8px;font-size:15px;font-weight:600;">
                Log in
              </a>
              <p style="margin:24px 0 8px;font-size:13px;color:#777;">
                Forgot your password? Use the "Forgot password" option on the login page.
              </p>
              <p style="margin:0;font-size:12px;color:#999;">
                If this wasn't you, you can safely ignore this email.
              </p>
            </td></tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""

        EmailService._deliver(to_email=to_email, subject=subject, html=html, text=text)

    @staticmethod
    def _deliver(*, to_email: str, subject: str, html: str, text: str) -> None:
        """Send one email through Resend, logging (not raising) on failure."""
        if not settings.EMAIL_ENABLED or not settings.RESEND_API_KEY:
            LOGGER.info(
                "[EMAIL:STUB] to=%s subject=%r (sending disabled or no API key)\n%s",
                to_email, subject, text,
            )
            return

        sender = (
            f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM}>"
            if settings.EMAIL_FROM_NAME
            else settings.EMAIL_FROM
        )

        params = {
            "from": sender,
            "to": [to_email],
            "subject": subject,
            "html": html,
            "text": text,
        }
        try:
            resend.api_key = settings.RESEND_API_KEY
            result = resend.Emails.send(params)  # type: ignore[arg-type]
            LOGGER.info(
                "Verification email sent to %s (resend id=%s)",
                to_email, (result or {}).get("id"),
            )
        except Exception as exc:  # noqa: BLE001 - never let email failure break the flow
            LOGGER.error("Failed to send email to %s via Resend: %s", to_email, exc)