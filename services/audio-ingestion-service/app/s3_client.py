import logging
from typing import BinaryIO
from app.config import settings

_logger = logging.getLogger(__name__)


def _client():
    try:
        import boto3
        return boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL or None,
            aws_access_key_id=settings.S3_ACCESS_KEY or None,
            aws_secret_access_key=settings.S3_SECRET_KEY or None,
            region_name=settings.S3_REGION,
        )
    except Exception as exc:
        _logger.warning("S3 client init failed: %s", exc)
        return None


def upload_chunk(file_obj: BinaryIO, s3_key: str, content_type: str) -> bool:
    """Upload audio bytes to S3. Returns True on success, False on any failure."""
    client = _client()
    if not client:
        _logger.warning("S3 unavailable — chunk %s not stored remotely", s3_key)
        return False
    try:
        client.upload_fileobj(
            file_obj,
            settings.S3_BUCKET,
            s3_key,
            ExtraArgs={"ContentType": content_type},
        )
        return True
    except Exception as exc:
        _logger.error("S3 upload failed for %s: %s", s3_key, exc)
        return False


def list_session_keys(user_id: str, session_id: str) -> list[str]:
    """List all S3 keys for a session's audio chunks."""
    client = _client()
    if not client:
        return []
    prefix = f"{user_id}/{session_id}/"
    try:
        paginator = client.get_paginator("list_objects_v2")
        keys = []
        for page in paginator.paginate(Bucket=settings.S3_BUCKET, Prefix=prefix):
            keys.extend(obj["Key"] for obj in page.get("Contents", []))
        return keys
    except Exception as exc:
        _logger.error("S3 list failed for prefix %s: %s", prefix, exc)
        return []


def delete_session_audio(user_id: str, session_id: str) -> int:
    """Delete all S3 objects for a session. Returns the number of objects deleted."""
    client = _client()
    if not client:
        return 0
    keys = list_session_keys(user_id, session_id)
    if not keys:
        return 0
    try:
        objects = [{"Key": k} for k in keys]
        client.delete_objects(Bucket=settings.S3_BUCKET, Delete={"Objects": objects})
        _logger.info("Deleted %d S3 objects for session %s", len(keys), session_id)
        return len(keys)
    except Exception as exc:
        _logger.error("S3 batch delete failed for session %s: %s", session_id, exc)
        return 0


def delete_user_audio(user_id: str) -> int:
    """Delete all S3 audio files for a user (GDPR account deletion). Returns count deleted."""
    client = _client()
    if not client:
        return 0
    prefix = f"{user_id}/"
    try:
        paginator = client.get_paginator("list_objects_v2")
        total = 0
        for page in paginator.paginate(Bucket=settings.S3_BUCKET, Prefix=prefix):
            objects = [{"Key": obj["Key"]} for obj in page.get("Contents", [])]
            if objects:
                client.delete_objects(Bucket=settings.S3_BUCKET, Delete={"Objects": objects})
                total += len(objects)
        _logger.info("GDPR: deleted %d S3 objects for user %s", total, user_id)
        return total
    except Exception as exc:
        _logger.error("S3 GDPR delete failed for user %s: %s", user_id, exc)
        return 0


def check_connectivity() -> bool:
    """Ping S3 by listing the bucket. Used by /ready health check."""
    client = _client()
    if not client:
        return False
    try:
        client.head_bucket(Bucket=settings.S3_BUCKET)
        return True
    except Exception:
        return False
