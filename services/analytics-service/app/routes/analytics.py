from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models import SleepSession, TimelineBucket
from app.security import get_current_user_id
from app.seed import seed_user

router = APIRouter()

@router.get("/timeline/{session_id}")
def get_timeline(
    session_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    session = db.query(SleepSession).filter(
        SleepSession.id == session_id, SleepSession.user_id == user_id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    buckets = (
        db.query(TimelineBucket)
        .filter(TimelineBucket.session_id == session_id)
        .order_by(TimelineBucket.bucket_index)
        .all()
    )
    return {
        "session_id": session_id,
        "bucket_size_minutes": 5,
        "buckets": [
            {
                "index": b.bucket_index,
                "offset_minutes": b.offset_minutes,
                "avg_intensity": b.avg_intensity,
                "dominant_class": b.dominant_class,
                "snore_event_count": b.snore_event_count,
            }
            for b in buckets
        ],
    }

@router.get("/trends")
def get_trends(
    period: str = "30d",
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    seed_user(user_id, db)
    days = {"7d": 7, "30d": 30, "90d": 90}.get(period, 30)
    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)

    sessions = (
        db.query(SleepSession)
        .filter(
            SleepSession.user_id == user_id,
            SleepSession.status == "complete",
            SleepSession.started_at >= since,
        )
        .order_by(SleepSession.started_at.asc())
        .all()
    )

    points = [
        {
            "date": s.started_at.strftime("%Y-%m-%d"),
            "quality_score": s.sleep_quality_score,
            "snoring_percentage": s.snoring_percentage,
            "duration_minutes": s.duration_minutes,
            "grade": s.sleep_quality_grade,
        }
        for s in sessions
    ]

    scores = [s.sleep_quality_score for s in sessions if s.sleep_quality_score]
    snore_pcts = [s.snoring_percentage for s in sessions if s.snoring_percentage]
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0
    avg_snore = round(sum(snore_pcts) / len(snore_pcts), 1) if snore_pcts else 0

    mid = len(scores) // 2
    first_half = sum(scores[:mid]) / max(len(scores[:mid]), 1)
    second_half = sum(scores[mid:]) / max(len(scores[mid:]), 1)
    diff = second_half - first_half
    trend = "improving" if diff > 3 else "declining" if diff < -3 else "stable"

    return {
        "period": period,
        "data_points": points,
        "summary": {
            "avg_quality_score": avg_score,
            "avg_snoring_percentage": avg_snore,
            "trend_direction": trend,
            "trend_change_percent": round(diff, 1),
            "nights_recorded": len(sessions),
            "nights_missed": days - len(sessions),
        },
    }

@router.get("/weekly-summary")
def weekly_summary(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    seed_user(user_id, db)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    week_start = now - timedelta(days=7)

    sessions = (
        db.query(SleepSession)
        .filter(
            SleepSession.user_id == user_id,
            SleepSession.status == "complete",
            SleepSession.started_at >= week_start,
        )
        .order_by(SleepSession.sleep_quality_score.desc())
        .all()
    )

    scores = [s.sleep_quality_score for s in sessions if s.sleep_quality_score]
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0
    best = sessions[0] if sessions else None
    worst = sessions[-1] if sessions else None

    prev_start = week_start - timedelta(days=7)
    prev_sessions = (
        db.query(SleepSession)
        .filter(
            SleepSession.user_id == user_id,
            SleepSession.status == "complete",
            SleepSession.started_at >= prev_start,
            SleepSession.started_at < week_start,
        )
        .all()
    )
    prev_scores = [s.sleep_quality_score for s in prev_sessions if s.sleep_quality_score]
    prev_avg = sum(prev_scores) / len(prev_scores) if prev_scores else avg_score

    return {
        "week_start": week_start.strftime("%Y-%m-%d"),
        "week_end": now.strftime("%Y-%m-%d"),
        "nights_recorded": len(sessions),
        "avg_quality_score": avg_score,
        "avg_snoring_percentage": round(
            sum(s.snoring_percentage or 0 for s in sessions) / max(len(sessions), 1), 1
        ),
        "avg_sleep_duration_minutes": int(
            sum(s.duration_minutes or 0 for s in sessions) / max(len(sessions), 1)
        ),
        "best_night": {
            "date": best.started_at.strftime("%Y-%m-%d"),
            "score": best.sleep_quality_score,
        } if best else None,
        "worst_night": {
            "date": worst.started_at.strftime("%Y-%m-%d"),
            "score": worst.sleep_quality_score,
        } if worst else None,
        "vs_previous_week": {
            "quality_change": round(avg_score - prev_avg, 1),
        },
    }
