"""Internal admin endpoints — called by auth-service for GDPR account deletion."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AudioChunk, SleepSession
from app.s3_client import delete_user_audio
from app.security import require_role

router = APIRouter()


@router.delete("/users/{user_id}/audio")
def gdpr_delete_user_audio(
    user_id: str,
    _admin: str = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Delete all S3 audio and ingestion DB records for a user (GDPR erasure)."""
    deleted_s3 = delete_user_audio(user_id)

    # Null out S3 keys for all chunks, then delete sessions
    session_ids = [r[0] for r in db.query(SleepSession.id).filter(SleepSession.user_id == user_id).all()]
    if session_ids:
        db.query(AudioChunk).filter(AudioChunk.session_id.in_(session_ids)).update(
            {"s3_key": None}, synchronize_session=False
        )
        db.query(SleepSession).filter(SleepSession.user_id == user_id).delete(synchronize_session=False)
        db.commit()

    return {
        "user_id": user_id,
        "s3_objects_deleted": deleted_s3,
        "sessions_deleted": len(session_ids),
    }
