"""Application exceptions aligned with RFC 9457 (Problem Details for HTTP APIs).

Field naming mirrors RFC 9457 members:
    - status_code -> response "status" + HTTP status line
    - title       -> response "title"
    - detail      -> response "detail"
    - code        -> response "code" extension member
    - errors      -> response "errors" extension member (optional)
"""
from typing import Any, Optional
from fastapi import status


class BaseAppException(Exception):
    """Base application exception. Raise these from services instead of HTTPException."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = "INTERNAL_SERVER_ERROR"
    title: str = "Internal Server Error"
    detail: str = "An unexpected error occurred."

    def __init__(
        self,
        detail: Optional[str] = None,
        *,
        title: Optional[str] = None,
        code: Optional[str] = None,
        status_code: Optional[int] = None,
        errors: Optional[Any] = None,
    ) -> None:
        if detail is not None:
            self.detail = detail
        if title is not None:
            self.title = title
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        self.errors = errors
        super().__init__(self.detail)


class BadRequestException(BaseAppException):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "BAD_REQUEST"
    title = "Bad Request"
    detail = "The request could not be processed."


class UnauthorizedException(BaseAppException):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "UNAUTHORIZED"
    title = "Unauthorized"
    detail = "Authentication is required to access this resource."


class ForbiddenException(BaseAppException):
    status_code = status.HTTP_403_FORBIDDEN
    code = "FORBIDDEN"
    title = "Forbidden"
    detail = "You do not have permission to perform this action."


class NotFoundException(BaseAppException):
    status_code = status.HTTP_404_NOT_FOUND
    code = "NOT_FOUND"
    title = "Not Found"
    detail = "The requested resource was not found."


class ConflictException(BaseAppException):
    status_code = status.HTTP_409_CONFLICT
    code = "CONFLICT"
    title = "Conflict"
    detail = "The request conflicts with the current state of the resource."


class UnprocessableEntityException(BaseAppException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "UNPROCESSABLE_ENTITY"
    title = "Unprocessable Entity"
    detail = "The request was well-formed but could not be processed."


class TooManyRequestsException(BaseAppException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "TOO_MANY_REQUESTS"
    title = "Too Many Requests"
    detail = "Rate limit exceeded. Please try again later."


class InternalServerException(BaseAppException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    code = "INTERNAL_SERVER_ERROR"
    title = "Internal Server Error"
    detail = "An internal server error occurred."


class ServiceUnavailableException(BaseAppException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "SERVICE_UNAVAILABLE"
    title = "Service Unavailable"
    detail = "The service is temporarily unavailable. Please try again later."


class DatabaseException(BaseAppException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    code = "DATABASE_ERROR"
    title = "Database Error"
    detail = "A database error occurred. Please try again."


class ExternalServiceException(BaseAppException):
    status_code = status.HTTP_502_BAD_GATEWAY
    code = "EXTERNAL_SERVICE_ERROR"
    title = "Bad Gateway"
    detail = "An external service request failed."