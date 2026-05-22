import json as _json
import logging
import urllib.request
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, UserHealthProfile, RefreshToken, SocialAccount, PasswordResetToken
from app.schemas import (
    UserResponse, UpdateProfileRequest,
    HealthProfileRequest, HealthProfileResponse,
)
from app.security import get_current_user_id
from app.redis_client import get_redis
from app.config import settings

_logger = logging.getLogger(__name__)

router = APIRouter()


def _profile_to_response(p: UserHealthProfile) -> HealthProfileResponse:
    return HealthProfileResponse(
        sleep_position=p.sleep_position,
        known_conditions=_json.loads(p.known_conditions) if p.known_conditions else None,
        medications=_json.loads(p.medications) if p.medications else None,
        alcohol_frequency=p.alcohol_frequency,
        smoking_status=p.smoking_status,
        cpap_user=p.cpap_user,
        snoring_severity_self=p.snoring_severity_self,
        updated_at=p.updated_at,
    )


@router.get("/me", response_model=UserResponse)
def get_me(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch("/me", response_model=UserResponse)
def update_me(
    body: UpdateProfileRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)
    return user


@router.get("/me/health-profile", response_model=HealthProfileResponse)
def get_health_profile(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    profile = db.query(UserHealthProfile).filter(UserHealthProfile.user_id == user_id).first()
    if not profile:
        return HealthProfileResponse()
    return _profile_to_response(profile)


@router.put("/me/health-profile", response_model=HealthProfileResponse)
def put_health_profile(
    body: HealthProfileRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    profile = db.query(UserHealthProfile).filter(UserHealthProfile.user_id == user_id).first()
    if not profile:
        profile = UserHealthProfile(user_id=user_id)
        db.add(profile)

    for field, value in body.model_dump(exclude_none=True).items():
        if field in ("known_conditions", "medications"):
            setattr(profile, field, _json.dumps(value))
        else:
            setattr(profile, field, value)

    db.commit()
    db.refresh(profile)
    return _profile_to_response(profile)


@router.delete("/me", status_code=204)
def delete_me(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Revoke Redis refresh tokens (best-effort; can't enumerate rt:{token} keys by user)
    r = get_redis()
    if r:
        try:
            tokens = db.query(RefreshToken).filter(
                RefreshToken.user_id == user_id, RefreshToken.is_revoked == False
            ).all()
            for t in tokens:
                r.delete(f"rt:{t.token}")
        except Exception:
            pass

    # Explicit cascade (SQLite may not enforce FK ON DELETE CASCADE)
    db.query(PasswordResetToken).filter(PasswordResetToken.user_id == user_id).delete()
    db.query(RefreshToken).filter(RefreshToken.user_id == user_id).delete()
    db.query(SocialAccount).filter(SocialAccount.user_id == user_id).delete()
    db.query(UserHealthProfile).filter(UserHealthProfile.user_id == user_id).delete()
    db.delete(user)
    db.commit()

    # Purge analytics-service data via internal endpoint
    if settings.ANALYTICS_SERVICE_URL:
        try:
            url = f"{settings.ANALYTICS_SERVICE_URL.rstrip('/')}/internal/users/{user_id}"
            req = urllib.request.Request(url, method="DELETE")
            with urllib.request.urlopen(req, timeout=5):
                pass
        except Exception:
            _logger.warning("analytics purge failed for user %s — data may remain", user_id, exc_info=True)

    return Response(status_code=204)
