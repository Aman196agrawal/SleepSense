from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from app.database import get_db
from app.models import LifestyleLog, SleepSession
from app.security import get_current_user_id
from app.patterns import generate_pattern_insights

router = APIRouter()


class LifestyleLogCreate(BaseModel):
    logged_date: str                                       # YYYY-MM-DD
    caffeine_cups: int     = Field(default=0, ge=0, le=10)
    alcohol_units: float   = Field(default=0.0, ge=0, le=20)
    exercise_minutes: int  = Field(default=0, ge=0, le=300)
    stress_level: int      = Field(default=3, ge=1, le=5)
    sleep_aid_used: bool   = False
    notes: Optional[str]   = None


@router.post("", status_code=201)
def log_lifestyle(
    body: LifestyleLogCreate,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    existing = db.query(LifestyleLog).filter(
        LifestyleLog.user_id == user_id,
        LifestyleLog.logged_date == body.logged_date,
    ).first()
    if existing:
        db.delete(existing)
        db.flush()

    log = LifestyleLog(
        user_id=user_id,
        logged_date=body.logged_date,
        caffeine_cups=body.caffeine_cups,
        alcohol_units=body.alcohol_units,
        exercise_minutes=body.exercise_minutes,
        stress_level=body.stress_level,
        sleep_aid_used=body.sleep_aid_used,
        notes=body.notes,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return _log_dict(log)


@router.get("")
def get_logs(
    days: int = 14,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    since = (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)).strftime("%Y-%m-%d")
    logs = (
        db.query(LifestyleLog)
        .filter(LifestyleLog.user_id == user_id, LifestyleLog.logged_date >= since)
        .order_by(LifestyleLog.logged_date.desc())
        .all()
    )
    return [_log_dict(l) for l in logs]


@router.get("/correlations")
def get_correlations(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    logs = (
        db.query(LifestyleLog)
        .filter(LifestyleLog.user_id == user_id)
        .order_by(LifestyleLog.logged_date.desc())
        .limit(60)
        .all()
    )
    sessions = (
        db.query(SleepSession)
        .filter(SleepSession.user_id == user_id, SleepSession.status == "complete")
        .order_by(SleepSession.started_at.desc())
        .limit(60)
        .all()
    )
    if not logs or not sessions:
        return {"correlations": [], "message": "Log at least a week of data to see correlations."}

    all_insights = generate_pattern_insights(user_id, sessions, logs)
    keywords = ("alcohol", "exercise", "stress", "caffeine")
    correlations = [i for i in all_insights if any(k in i["title"].lower() for k in keywords)]
    return {"correlations": correlations}


def _log_dict(log: LifestyleLog) -> dict:
    return {
        "id": log.id,
        "logged_date": log.logged_date,
        "caffeine_cups": log.caffeine_cups,
        "alcohol_units": log.alcohol_units,
        "exercise_minutes": log.exercise_minutes,
        "stress_level": log.stress_level,
        "sleep_aid_used": log.sleep_aid_used,
        "notes": log.notes,
        "created_at": log.created_at.isoformat(),
    }
