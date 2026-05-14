"""
Device token routes:
  POST   /device-tokens        — register FCM or APNs token (idempotent)
  GET    /device-tokens        — list own tokens
  DELETE /device-tokens/{token} — unregister
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import DeviceToken
from app.push_client import VALID_PLATFORMS
from app.security import get_current_user_id

router = APIRouter()

PLATFORM_VALUES = sorted(VALID_PLATFORMS)


class TokenIn(BaseModel):
    token:    str
    platform: str   # "fcm" | "apns"


class TokenOut(BaseModel):
    id:         str
    token:      str
    platform:   str
    created_at: str

    @classmethod
    def from_orm(cls, dt: DeviceToken) -> "TokenOut":
        return cls(
            id=dt.id,
            token=dt.token,
            platform=dt.platform,
            created_at=dt.created_at.isoformat(),
        )


@router.post("", status_code=200)
def register_token(
    body:    TokenIn,
    user_id: str     = Depends(get_current_user_id),
    db:      Session = Depends(get_db),
):
    if body.platform not in VALID_PLATFORMS:
        raise HTTPException(
            status_code=422,
            detail=f"platform must be one of {PLATFORM_VALUES}",
        )
    existing = (
        db.query(DeviceToken)
        .filter(DeviceToken.user_id == user_id, DeviceToken.token == body.token)
        .first()
    )
    if existing:
        return TokenOut.from_orm(existing)   # idempotent
    dt = DeviceToken(user_id=user_id, token=body.token, platform=body.platform)
    db.add(dt)
    db.commit()
    db.refresh(dt)
    return TokenOut.from_orm(dt)


@router.get("")
def list_tokens(
    user_id: str     = Depends(get_current_user_id),
    db:      Session = Depends(get_db),
):
    tokens = db.query(DeviceToken).filter(DeviceToken.user_id == user_id).all()
    return {"tokens": [TokenOut.from_orm(t) for t in tokens]}


@router.delete("/{token}", status_code=204)
def unregister_token(
    token:   str,
    user_id: str     = Depends(get_current_user_id),
    db:      Session = Depends(get_db),
):
    dt = (
        db.query(DeviceToken)
        .filter(DeviceToken.token == token)
        .first()
    )
    if not dt:
        raise HTTPException(status_code=404, detail="Token not found")
    if dt.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not your token")
    db.delete(dt)
    db.commit()
