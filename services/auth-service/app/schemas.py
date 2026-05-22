import re
from pydantic import BaseModel, EmailStr, ConfigDict, Field, field_validator
from typing import Optional, List, Literal
from datetime import datetime


def _validate_password_strength(v: str) -> str:
    errors = []
    if len(v) < 8:
        errors.append('at least 8 characters')
    if not re.search(r'[A-Z]', v):
        errors.append('one uppercase letter')
    if not re.search(r'\d', v):
        errors.append('one number')
    if not re.search(r'[!@#$%^&*()\-_=+\[\]{};:\'",.<>?/\\|`~]', v):
        errors.append('one special character')
    if errors:
        raise ValueError(f"Password must contain: {', '.join(errors)}")
    return v


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: str

    @field_validator('password')
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _validate_password_strength(v)

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RefreshRequest(BaseModel):
    refresh_token: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

class UserResponse(BaseModel):
    id: str
    email: str
    display_name: Optional[str]
    weight_kg: Optional[float]
    height_cm: Optional[float]
    timezone: str
    bedtime_reminder_time: Optional[str] = None
    is_verified: bool = False
    role: str = "user"
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class UpdateProfileRequest(BaseModel):
    display_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    weight_kg: Optional[float] = Field(default=None, ge=0, le=500)
    height_cm: Optional[float] = Field(default=None, ge=0, le=300)
    timezone: Optional[str] = None
    bedtime_reminder_time: Optional[str] = None

class HealthProfileRequest(BaseModel):
    sleep_position: Optional[Literal["back", "side", "stomach"]] = None
    known_conditions: Optional[List[str]] = None
    medications: Optional[List[str]] = None
    alcohol_frequency: Optional[Literal["never", "occasionally", "regularly"]] = None
    smoking_status: Optional[Literal["never", "former", "current"]] = None
    cpap_user: Optional[bool] = None
    snoring_severity_self: Optional[int] = Field(None, ge=1, le=5)

class HealthProfileResponse(BaseModel):
    sleep_position: Optional[str] = None
    known_conditions: Optional[List[str]] = None
    medications: Optional[List[str]] = None
    alcohol_frequency: Optional[str] = None
    smoking_status: Optional[str] = None
    cpap_user: Optional[bool] = None
    snoring_severity_self: Optional[int] = None
    updated_at: Optional[datetime] = None

class SocialLoginRequest(BaseModel):
    id_token: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    @field_validator('new_password')
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _validate_password_strength(v)


class VerifyEmailRequest(BaseModel):
    token: str
