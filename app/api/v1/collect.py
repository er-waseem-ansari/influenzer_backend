"""Public conversion postback endpoint.

``POST /collect/event`` — a brand's server reports a conversion. Authentication
(HMAC signature, timestamp window, replay nonce, rate limit) is handled entirely
by the ``verify_postback`` dependency; the handler only parses the *verified* raw
bytes and delegates to the service.

The body is parsed from ``verified.raw_body`` (not via FastAPI body binding) so the
signature is checked against the exact bytes the brand signed. A schema/JSON
failure is the only ``400`` here; all auth failures already became a generic
``401`` upstream.
"""
from fastapi import APIRouter, Depends
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestException
from app.core.postback_security import VerifiedPostback, verify_postback
from app.database import get_db
from app.schemas.postback import POSTBACK_EVENT_ADAPTER, PostbackAccepted
from app.services.postback_service import PostbackService

router = APIRouter(prefix="/collect", tags=["Postback"])


@router.post("/event", response_model=PostbackAccepted)
async def collect_event(
    verified: VerifiedPostback = Depends(verify_postback),
    db: Session = Depends(get_db),
) -> PostbackAccepted:
    try:
        event = POSTBACK_EVENT_ADAPTER.validate_json(verified.raw_body)
    except ValidationError:
        # Malformed/incomplete payload — distinct from an auth failure (400 vs 401).
        raise BadRequestException("The postback payload is malformed or incomplete.")
    return PostbackService.process(db, verified, event)
