"""
Insight routes:
  POST  /insights/generate          — evaluate rules, store, return insights
  GET   /insights?session_id=<uuid> — fetch stored insights for a session (up to 3)
  PATCH /insights/{id}/read         — mark insight as read
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import SessionInsight
from app.security import get_current_user_id

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    session_id:           str
    sleep_quality_score:  float
    snore_ratio:          float
    avg_snore_intensity:  float          = 0.0
    duration_minutes:     int            = 480
    peak_snoring_hour:    Optional[int]  = None
    recent_scores:        List[float]    = []
    recent_durations:     List[int]      = []
    alcohol_units_today:  float          = 0.0
    sleep_position:       Optional[str]  = None


class InsightOut(BaseModel):
    id:           str
    session_id:   str
    insight_type: str
    priority:     int
    title:        str
    body:         str
    action_url:   Optional[str]
    is_read:      bool
    created_at:   str

    @classmethod
    def from_orm(cls, ins: SessionInsight) -> "InsightOut":
        return cls(
            id           = ins.id,
            session_id   = ins.session_id,
            insight_type = ins.insight_type,
            priority     = ins.priority,
            title        = ins.title,
            body         = ins.body,
            action_url   = ins.action_url,
            is_read      = ins.is_read,
            created_at   = ins.created_at.isoformat(),
        )


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/generate")
def generate_insights(
    body:    GenerateRequest,
    user_id: str     = Depends(get_current_user_id),
    db:      Session = Depends(get_db),
):
    from app.rules import evaluate_rules
    from app.kafka_producer import emit
    from app.config import settings

    rule_insights = evaluate_rules(
        sleep_quality_score = body.sleep_quality_score,
        snore_ratio         = body.snore_ratio,
        avg_snore_intensity = body.avg_snore_intensity,
        duration_minutes    = body.duration_minutes,
        recent_scores       = body.recent_scores,
        recent_durations    = body.recent_durations,
        alcohol_units_today = body.alcohol_units_today,
        sleep_position      = body.sleep_position,
    )

    created = []
    for ri in rule_insights:
        ins = SessionInsight(
            session_id   = body.session_id,
            user_id      = user_id,
            insight_type = ri["insight_type"],
            priority     = ri["priority"],
            title        = ri["title"],
            body         = ri["body"],
            action_url   = ri.get("action_url"),
        )
        db.add(ins)
        created.append((ins, ri))

    db.commit()
    for ins, _ in created:
        db.refresh(ins)

    # Push notification for CHRONIC_SNORING
    for ins, ri in created:
        if ri.get("rule_name") == "CHRONIC_SNORING":
            emit(settings.KAFKA_NOTIFICATION_TOPIC, {
                "user_id":  user_id,
                "type":     "health_alert",
                "title":    ri["title"],
                "body":     ri["body"],
                "channels": ["push", "in_app"],
            })

    return [InsightOut.from_orm(ins) for ins, _ in created]


@router.get("")
def get_insights(
    session_id: str,
    user_id:    str     = Depends(get_current_user_id),
    db:         Session = Depends(get_db),
):
    insights = (
        db.query(SessionInsight)
        .filter(
            SessionInsight.session_id == session_id,
            SessionInsight.user_id    == user_id,
        )
        .order_by(SessionInsight.priority.desc())
        .limit(3)
        .all()
    )
    return [InsightOut.from_orm(i) for i in insights]


@router.patch("/{insight_id}/read")
def mark_read(
    insight_id: str,
    user_id:    str     = Depends(get_current_user_id),
    db:         Session = Depends(get_db),
):
    ins = db.query(SessionInsight).filter(SessionInsight.id == insight_id).first()
    if not ins:
        return {"id": insight_id, "is_read": True}
    if ins.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not your insight")
    ins.is_read = True
    db.commit()
    return InsightOut.from_orm(ins)
