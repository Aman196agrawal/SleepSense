"""Internal admin endpoints — called by auth-service for GDPR account deletion."""
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import AudioChunk, SleepSession
from app.s3_client import delete_user_audio

router = APIRouter()


@router.delete("/users/{user_id}/audio")
def gdpr_delete_user_audio(
    user_id: str,
    x_internal_secret: str = Header(..., alias="X-Internal-Secret"),
    db: Session = Depends(get_db),
):
    # Fail closed: an unconfigured (empty) secret must never authorise this
    # destructive GDPR endpoint, otherwise an empty header would match.
    if not settings.INTERNAL_API_SECRET or x_internal_secret != settings.INTERNAL_API_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")
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
