import json as _json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, UserHealthProfile
from app.schemas import (
    UserResponse, UpdateProfileRequest,
    HealthProfileRequest, HealthProfileResponse,
)
from app.security import get_current_user_id

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
