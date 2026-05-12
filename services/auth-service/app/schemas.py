from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional
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
