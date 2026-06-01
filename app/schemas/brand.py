import re

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

# bcrypt silently ignores anything past the first 72 bytes, so we cap there.
PASSWORD_MAX_LENGTH = 72


class BrandSignupRequest(BaseModel):
    """First-time brand admin signup. Only email + password are required;
    company/profile details are filled in later via profile-update APIs."""
    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    email: EmailStr = Field(...)
    password: str = Field(..., min_length=8, max_length=PASSWORD_MAX_LENGTH)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        if len(value.encode("utf-8")) > PASSWORD_MAX_LENGTH:
            raise ValueError("Password must be at most 72 bytes long.")
        if not re.search(r"[A-Za-z]", value):
            raise ValueError("Password must contain at least one letter.")
        if not re.search(r"\d", value):
            raise ValueError("Password must contain at least one digit.")
        return value


class BrandLoginRequest(BaseModel):
    """Email + password login for brand-side users. Password strength is not
    re-validated here (that is a signup concern); we only require a non-empty
    value within bcrypt's effective length."""
    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    email: EmailStr = Field(...)
    password: str = Field(..., min_length=1, max_length=PASSWORD_MAX_LENGTH)
    device_info: str | None = Field(default=None, alias="deviceInfo")


class MessageResponse(BaseModel):
    """Minimal response carrying only a human-readable message."""
    message: str

class ResendVerificationRequest(BaseModel):
    email: EmailStr = Field(...)


class BrandSignoutRequest(BaseModel):
    """Sign out a brand session. `refresh_token` is the token issued at login
    that should be revoked. Set `all_devices` to revoke every active refresh
    token for the caller instead of just this one."""
    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    refresh_token: str | None = Field(default=None, alias="refreshToken", min_length=1)
    all_devices: bool = Field(default=False, alias="allDevices")