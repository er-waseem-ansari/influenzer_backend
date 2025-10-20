# core/google_auth.py

from google.auth.transport import requests
from google.oauth2 import id_token
from fastapi import HTTPException, status
from app.config import get_settings

settings = get_settings()


async def verify_google_token(token_str: str) -> dict:
    """
    Verify Google ID token and return user info.

    Args:
        token_str: Google ID token from Flutter

    Returns:
        dict: User info with keys: sub (google_id), email, name, picture

    Raises:
        HTTPException: If token is invalid
    """
    try:
        # Verify the token with Google's servers
        idinfo = id_token.verify_oauth2_token(
            token_str,
            requests.Request(),
            settings.GOOGLE_CLIENT_ID
        )

        # Token is valid, return user info
        return {
            'sub': idinfo['sub'],  # Google user ID
            'email': idinfo.get('email'),  # Email (verified by Google)
            'name': idinfo.get('name'),  # Full name
            'picture': idinfo.get('picture'),  # Profile picture URL
            'email_verified': idinfo.get('email_verified', False)
        }

    except ValueError as e:
        # Token is invalid or expired
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Google token: {str(e)}"
        )
    except Exception as e:
        # Other errors (network, etc.)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error verifying Google token: {str(e)}"
        )