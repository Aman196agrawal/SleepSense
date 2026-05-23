from datetime import datetime, timezone
from typing import Literal, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import UserGoal, SleepSession
from app.security import get_current_user_id

router = APIRouter()


class GoalCreate(BaseModel):
    goal_type:    Literal["quality_score", "recording_streak"]
    target_value: float = Field(..., gt=0)
    target_date:  Optional[str] = None


def _compute_current(goal: UserGoal, db: Session, user_id: str) -> float:
    if goal.goal_type == "quality_score":
        sessions = (
            db.query(SleepSession)
            .filter(SleepSession.user_id == user_id, SleepSession.status == "complete")
            .order_by(SleepSession.started_at.desc())
            .limit(7)
            .all()
        )
        scores = [s.sleep_quality_score for s in sessions if s.sleep_quality_score]
        return round(sum(scores) / len(scores), 1) if scores else 0.0

    if goal.goal_type == "recording_streak":
        from datetime import timedelta
        sessions = (
            db.query(SleepSession)
            .filter(SleepSession.user_id == user_id, SleepSession.status == "complete")
            .order_by(SleepSession.started_at.desc())
            .all()
        )
        dates = sorted({s.started_at.date() for s in sessions if s.started_at}, reverse=True)
        today = datetime.now(timezone.utc).date()
        streak = 0
        for i, d in enumerate(dates):
            if d == today - timedelta(days=i):
                streak += 1
            else:
                break
        return float(streak)

    return 0.0


def _goal_dict(goal: UserGoal) -> dict:
    return {
        "id": goal.id,
        "goal_type": goal.goal_type,
        "target_value": goal.target_value,
        "current_value": goal.current_value,
        "is_achieved": goal.is_achieved,
        "target_date": goal.target_date,
        "progress_pct": round(min(goal.current_value / goal.target_value * 100, 100), 1) if goal.target_value else 0,
        "created_at": goal.created_at.isoformat(),
    }


@router.post("", status_code=201)
def create_goal(
    body: GoalCreate,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    existing = db.query(UserGoal).filter(
        UserGoal.user_id == user_id,
        UserGoal.goal_type == body.goal_type,
        UserGoal.is_achieved == False,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="An active goal of this type already exists. Complete or delete it first.")

    goal = UserGoal(
        user_id=user_id,
        goal_type=body.goal_type,
        target_value=body.target_value,
        target_date=body.target_date,
    )
    goal.current_value = _compute_current(goal, db, user_id)
    if goal.current_value >= goal.target_value:
        goal.is_achieved = True
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return _goal_dict(goal)


@router.get("")
def list_goals(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    goals = (
        db.query(UserGoal)
        .filter(UserGoal.user_id == user_id)
        .order_by(UserGoal.created_at.desc())
        .all()
    )
    # Return stored values only — progress is refreshed by update_goals_for_user()
    # which is called at session end so GET remains a safe, read-only operation.
    return [_goal_dict(g) for g in goals]


def update_goals_for_user(user_id: str, db: Session) -> None:
    """Recompute and persist goal progress. Called after session end."""
    from app.kafka_client import emit
    goals = db.query(UserGoal).filter(
        UserGoal.user_id == user_id, UserGoal.is_achieved == False
    ).all()
    newly_achieved = []
    for goal in goals:
        goal.current_value = _compute_current(goal, db, user_id)
        if goal.current_value >= goal.target_value:
            goal.is_achieved = True
            newly_achieved.append(goal)
    if goals:
        db.commit()

    # Emit achievement badge notification for each newly completed goal (FR-NOTIF-004)
    label_map = {"quality_score": "Sleep Quality Score", "recording_streak": "Recording Streak"}
    for goal in newly_achieved:
        label = label_map.get(goal.goal_type, goal.goal_type.replace("_", " ").title())
        try:
            emit("notification.send", {
                "user_id": user_id,
                "type": "achievement",
                "title": "Goal achieved! \U0001f3c6",
                "body": f"You reached your {label} goal of {goal.target_value:.0f}. Keep it up!",
                "payload": {"goal_id": goal.id, "goal_type": goal.goal_type, "screen": "Goals"},
                "channels": ["push", "in_app"],
            })
        except Exception:
            pass  # Never block session completion because of a notification failure


@router.delete("/{goal_id}", status_code=204)
def delete_goal(
    goal_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    goal = db.query(UserGoal).filter(UserGoal.id == goal_id, UserGoal.user_id == user_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    db.delete(goal)
    db.commit()
    from fastapi import Response
    return Response(status_code=204)
