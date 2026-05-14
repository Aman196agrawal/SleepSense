from pydantic import BaseModel, EmailStr, ConfigDict, Field
from typing import Optional, List, Literal
from datetime import datetime

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: str

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
    weight_kg: Optional[str]
    height_cm: Optional[str]
    timezone: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class UpdateProfileRequest(BaseModel):
    display_name: Optional[str] = None
    weight_kg: Optional[str] = None
    height_cm: Optional[str] = None
    timezone: Optional[str] = None

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
