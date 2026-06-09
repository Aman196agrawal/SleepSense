import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import SessionInsight, SleepSession, LifestyleLog
from app.security import get_current_user_id
from app.seed import seed_user
from app.patterns import generate_pattern_insights

router = APIRouter()


@router.get("")
def get_insights(
    limit: int = 10,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    seed_user(user_id, db)

    sessions = (
        db.query(SleepSession)
        .filter(SleepSession.user_id == user_id, SleepSession.status == "complete")
        .order_by(SleepSession.started_at.desc())
        .limit(30)
        .all()
    )
    lifestyle_logs = (
        db.query(LifestyleLog)
        .filter(LifestyleLog.user_id == user_id)
        .order_by(LifestyleLog.logged_date.desc())
        .limit(30)
        .all()
    )

    # Pattern-based insights from real data
    pattern_insights = generate_pattern_insights(user_id, sessions, lifestyle_logs)

    # Stored insights from session-end events (most recent 5)
    stored = (
        db.query(SessionInsight)
        .filter(SessionInsight.user_id == user_id)
        .order_by(SessionInsight.created_at.desc())
        .limit(5)
        .all()
    )

    stored_dicts = [
        {
            "id": i.id,
            "session_id": i.session_id,
            "insight_type": i.insight_type,
            "priority": i.priority,
            "title": i.title,
            "body": i.body,
            "is_read": i.is_read,
            "created_at": i.created_at.isoformat(),
            "source": "session",
        }
        for i in stored
    ]

    # Merge: pattern insights take priority, avoid duplicate titles
    seen = {i["title"] for i in stored_dicts}
    pattern_dicts = []
    for pi in pattern_insights:
        if pi["title"] not in seen:
            pattern_dicts.append({
                "id": str(uuid.uuid4()),
                "session_id": None,
                "insight_type": pi["type"],
                "priority": pi.get("priority", 5),
                "title": pi["title"],
                "body": pi["body"],
                "is_read": False,
                "created_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
                "source": "pattern",
            })
            seen.add(pi["title"])

    all_insights = pattern_dicts + stored_dicts
    all_insights.sort(key=lambda x: x.get("priority", 0), reverse=True)
    return all_insights[:limit]


@router.patch("/{insight_id}/read")
def mark_read(
    insight_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    insight = db.query(SessionInsight).filter(
        SessionInsight.id == insight_id,
        SessionInsight.user_id == user_id,
    ).first()
    if not insight:
        raise HTTPException(status_code=404, detail="Insight not found")

    insight.is_read = True
    db.commit()
    return {"id": insight_id, "is_read": True}
