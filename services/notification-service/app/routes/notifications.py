"""
Notification routes:
  GET  /notifications              — list own notifications (paginated)
  GET  /notifications/unread-count — unread count
  PATCH /notifications/{id}/read  — mark one as read
  POST /notifications/mark-all-read — bulk mark read
"""
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Notification
from app.security import get_current_user_id

router = APIRouter()


def _parse_json_payload(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        result = json.loads(raw)
        return result if isinstance(result, dict) else {}
    except (json.JSONDecodeError, ValueError):
        return {}


# ── Response schema ───────────────────────────────────────────────────────────

class NotificationOut(BaseModel):
    id:         str
    type:       str
    title:      str
    body:       str
    payload:    dict
    channel:    str
    is_read:    bool
    sent_at:    str | None
    created_at: str

    @classmethod
    def from_orm(cls, n: Notification) -> "NotificationOut":
        return cls(
            id=n.id,
            type=n.type,
            title=n.title,
            body=n.body,
            payload=_parse_json_payload(n.payload),
            channel=n.channel,
            is_read=n.is_read,
            sent_at=n.sent_at.isoformat() if n.sent_at else None,
            created_at=n.created_at.isoformat(),
        )


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("")
def list_notifications(
    limit:   int = Query(20, ge=1, le=100),
    offset:  int = Query(0, ge=0),
    user_id: str = Depends(get_current_user_id),
    db:      Session = Depends(get_db),
):
    rows = (
        db.query(Notification)
        .filter(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    total = db.query(Notification).filter(Notification.user_id == user_id).count()
    return {"total": total, "notifications": [NotificationOut.from_orm(n) for n in rows]}


@router.get("/unread-count")
def unread_count(
    user_id: str = Depends(get_current_user_id),
    db:      Session = Depends(get_db),
):
    count = (
        db.query(Notification)
        .filter(Notification.user_id == user_id, Notification.is_read == False)
        .count()
    )
    return {"unread_count": count}


@router.patch("/{notif_id}/read")
def mark_read(
    notif_id: str,
    user_id:  str = Depends(get_current_user_id),
    db:       Session = Depends(get_db),
):
    notif = db.query(Notification).filter(Notification.id == notif_id).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    if notif.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not your notification")
    notif.is_read = True
    db.commit()
    return NotificationOut.from_orm(notif)


@router.post("/mark-all-read")
def mark_all_read(
    user_id: str = Depends(get_current_user_id),
    db:      Session = Depends(get_db),
):
    updated = (
        db.query(Notification)
        .filter(Notification.user_id == user_id, Notification.is_read == False)
        .update({"is_read": True})
    )
    db.commit()
    return {"marked_read": updated}
