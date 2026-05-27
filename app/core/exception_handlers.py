"""Global exception handlers following RFC 9457 (Problem Details for HTTP APIs).

https://www.rfc-editor.org/rfc/rfc9457.html
"""
import http
import logging
from typing import Any, Optional

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import BaseAppException

LOGGER = logging.getLogger(__name__)

PROBLEM_JSON_CONTENT_TYPE = "application/problem+json"
DEFAULT_PROBLEM_TYPE = "about:blank"


class ProblemDetailsResponse(JSONResponse):
    media_type = PROBLEM_JSON_CONTENT_TYPE


def _http_phrase(status_code: int) -> str:
    try:
        return http.HTTPStatus(status_code).phrase
    except ValueError:
        return "Error"


def _build_problem_response(
    request: Request,
    status_code: int,
    title: str,
    detail: str,
    code: Optional[str] = None,
    type_uri: str = DEFAULT_PROBLEM_TYPE,
    extensions: Optional[dict[str, Any]] = None,
) -> ProblemDetailsResponse:
    body: dict[str, Any] = {
        "type": type_uri,
        "title": title,
        "status": status_code,
        "detail": detail,
        "instance": str(request.url.path),
    }
    if code:
        body["code"] = code
    if extensions:
        body.update(extensions)
    return ProblemDetailsResponse(status_code=status_code, content=body)


async def app_exception_handler(request: Request, exc: BaseAppException) -> ProblemDetailsResponse:
    LOGGER.warning(
        "AppException at %s: [%s] %s",
        request.url.path,
        exc.code,
        exc.detail,
    )
    extensions: dict[str, Any] = {}
    if exc.errors is not None:
        extensions["errors"] = exc.errors

    return _build_problem_response(
        request=request,
        status_code=exc.status_code,
        title=exc.title,
        detail=exc.detail,
        code=exc.code,
        extensions=extensions,
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> ProblemDetailsResponse:
    LOGGER.warning(
        "HTTPException at %s: %s - %s",
        request.url.path,
        exc.status_code,
        exc.detail,
    )
    detail = str(exc.detail) if exc.detail is not None else _http_phrase(exc.status_code)
    return _build_problem_response(
        request=request,
        status_code=exc.status_code,
        title=_http_phrase(exc.status_code),
        detail=detail,
        code=f"HTTP_{exc.status_code}",
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> ProblemDetailsResponse:
    errors = []
    for err in exc.errors():
        loc = [str(part) for part in err.get("loc", []) if part != "body"]
        errors.append({
            "field": ".".join(loc) if loc else None,
            "message": err.get("msg"),
            "type": err.get("type"),
        })

    LOGGER.warning("Validation error at %s: %s", request.url.path, errors)
    return _build_problem_response(
        request=request,
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        title="Unprocessable Entity",
        detail="One or more request parameters failed validation.",
        code="VALIDATION_ERROR",
        extensions={"errors": errors},
    )


async def integrity_error_handler(request: Request, exc: IntegrityError) -> ProblemDetailsResponse:
    LOGGER.error(
        "IntegrityError at %s: %s",
        request.url.path,
        str(exc.orig) if exc.orig else str(exc),
    )
    return _build_problem_response(
        request=request,
        status_code=status.HTTP_409_CONFLICT,
        title="Conflict",
        detail="A data integrity error occurred. The resource may already exist or violate constraints.",
        code="DATABASE_INTEGRITY_ERROR",
    )


async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError) -> ProblemDetailsResponse:
    LOGGER.exception("SQLAlchemyError at %s: %s", request.url.path, exc)
    return _build_problem_response(
        request=request,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        title="Internal Server Error",
        detail="A database error occurred. Please try again.",
        code="DATABASE_ERROR",
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> ProblemDetailsResponse:
    LOGGER.exception("Unhandled exception at %s: %s", request.url.path, exc)
    return _build_problem_response(
        request=request,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        title="Internal Server Error",
        detail="An unexpected error occurred. Please try again later.",
        code="INTERNAL_SERVER_ERROR",
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all global exception handlers on the FastAPI app."""
    app.add_exception_handler(BaseAppException, app_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(IntegrityError, integrity_error_handler)
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
