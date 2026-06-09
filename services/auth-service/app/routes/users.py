import io
import json as _json
import logging
import urllib.request
from fastapi import APIRouter, Depends, File, Header, HTTPException, Response, UploadFile
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

_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
_MAX_AVATAR_BYTES = 5 * 1024 * 1024  # 5 MB

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


@router.post("/me/avatar", response_model=UserResponse)
async def upload_avatar(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Upload a profile avatar to S3 and store the CDN URL (FR-AUTH-008)."""
    if not settings.S3_BUCKET_ASSETS:
        raise HTTPException(status_code=503, detail="Avatar upload not configured")

    content_type = file.content_type or ""
    if content_type not in _ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Only JPEG, PNG, or WebP images accepted")

    data = await file.read()
    if len(data) > _MAX_AVATAR_BYTES:
        raise HTTPException(status_code=413, detail="Image exceeds 5 MB limit")

    # Always store as .jpg for consistency; use user_id as stable key so each
    # upload overwrites the previous avatar rather than accumulating orphan files.
    s3_key = f"profiles/{user_id}/avatar.jpg"
    try:
        import boto3
        client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL or None,
            aws_access_key_id=settings.S3_ACCESS_KEY or None,
            aws_secret_access_key=settings.S3_SECRET_KEY or None,
            region_name=settings.S3_REGION,
        )
        client.upload_fileobj(
            io.BytesIO(data),
            settings.S3_BUCKET_ASSETS,
            s3_key,
            ExtraArgs={"ContentType": "image/jpeg"},
        )
    except Exception as exc:
        _logger.error("Avatar S3 upload failed for user %s: %s", user_id, exc)
        raise HTTPException(status_code=502, detail="Upload failed — please try again")

    if settings.CDN_BASE_URL:
        image_url = f"{settings.CDN_BASE_URL.rstrip('/')}/{s3_key}"
    else:
        base = settings.S3_ENDPOINT_URL or f"https://{settings.S3_BUCKET_ASSETS}.s3.{settings.S3_REGION}.amazonaws.com"
        image_url = f"{base.rstrip('/')}/{s3_key}"

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.profile_image_url = image_url
    db.commit()
    db.refresh(user)
    return user


@router.get("/internal/with-reminder/{hhmm}", include_in_schema=False)
def users_with_reminder(
    hhmm: str,
    x_internal_secret: str | None = Header(None, alias="X-Internal-Secret"),
    db: Session = Depends(get_db),
):
    """Internal endpoint used by notification-service to send bedtime reminders (FR-GOAL-001).
    Protected by a shared secret header — never call from untrusted clients."""
    if not settings.INTERNAL_API_SECRET or x_internal_secret != settings.INTERNAL_API_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")
    users = db.query(User).filter(
        User.bedtime_reminder_time == hhmm,
        User.is_active == True,
    ).all()
    return [{"id": u.id, "email": u.email} for u in users]


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
            if settings.INTERNAL_API_SECRET:
                req.add_header("X-Internal-Secret", settings.INTERNAL_API_SECRET)
            with urllib.request.urlopen(req, timeout=5):
                pass
        except Exception:
            _logger.warning("analytics purge failed for user %s — data may remain", user_id, exc_info=True)

    return Response(status_code=204)
