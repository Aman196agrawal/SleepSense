import logging
import os
import shutil
from typing import BinaryIO
from app.config import settings

_logger = logging.getLogger(__name__)


# ── Local-disk backend ────────────────────────────────────────────────────────
# Selected with AUDIO_STORAGE_BACKEND=local. Stores each chunk as a real file at
# AUDIO_STORAGE_DIR/<s3_key>, so the same key layout works with or without S3 and
# nothing else in the service has to care which backend is active. Exists because
# requiring Docker + MinIO purely to keep audio is a heavy dependency for local
# dev — the same reasoning that has auth and analytics on SQLite instead of
# Postgres here.

def _use_local() -> bool:
    return settings.AUDIO_STORAGE_BACKEND.strip().lower() == "local"


def _local_path(s3_key: str) -> str:
    """Resolve a key under the storage root, refusing anything that escapes it."""
    root = os.path.abspath(settings.AUDIO_STORAGE_DIR)
    path = os.path.abspath(os.path.join(root, s3_key))
    if not (path == root or path.startswith(root + os.sep)):
        raise ValueError(f"key escapes the storage root: {s3_key!r}")
    return path


def _local_upload(file_obj: BinaryIO, s3_key: str) -> bool:
    try:
        path = _local_path(s3_key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            shutil.copyfileobj(file_obj, fh)
        return True
    except Exception as exc:
        _logger.error("local store failed for %s: %s", s3_key, exc)
        return False


def _local_list(prefix: str) -> list[str]:
    try:
        base = _local_path(prefix)
    except ValueError:
        return []
    if not os.path.isdir(base):
        return []
    root = os.path.abspath(settings.AUDIO_STORAGE_DIR)
    keys = []
    for dirpath, _dirs, files in os.walk(base):
        for name in files:
            full = os.path.join(dirpath, name)
            keys.append(os.path.relpath(full, root).replace(os.sep, "/"))
    return sorted(keys)


def _local_delete_prefix(prefix: str) -> int:
    keys = _local_list(prefix)
    removed = 0
    for k in keys:
        try:
            os.remove(_local_path(k))
            removed += 1
        except Exception as exc:
            _logger.error("local delete failed for %s: %s", k, exc)
    # Tidy up now-empty session/user directories.
    try:
        base = _local_path(prefix)
        for dirpath, _dirs, _files in os.walk(base, topdown=False):
            if not os.listdir(dirpath):
                os.rmdir(dirpath)
    except Exception:
        pass
    return removed


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
    """Store audio bytes. Returns True on success, False on any failure."""
    if _use_local():
        return _local_upload(file_obj, s3_key)
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
    """List all storage keys for a session's audio chunks."""
    if _use_local():
        return _local_list(f"{user_id}/{session_id}/")
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
    """Delete all stored audio for a session. Returns the number removed."""
    if _use_local():
        n = _local_delete_prefix(f"{user_id}/{session_id}/")
        _logger.info("Deleted %d local audio files for session %s", n, session_id)
        return n
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
    """Delete all audio for a user (GDPR account deletion). Returns count deleted."""
    if _use_local():
        n = _local_delete_prefix(f"{user_id}/")
        _logger.info("GDPR: deleted %d local audio files for user %s", n, user_id)
        return n
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
    """Verify the storage backend is usable. Used by the /ready health check."""
    if _use_local():
        try:
            os.makedirs(os.path.abspath(settings.AUDIO_STORAGE_DIR), exist_ok=True)
            return os.access(os.path.abspath(settings.AUDIO_STORAGE_DIR), os.W_OK)
        except Exception as exc:
            _logger.error("local storage dir unusable: %s", exc)
            return False
    client = _client()
    if not client:
        return False
    try:
        client.head_bucket(Bucket=settings.S3_BUCKET)
        return True
    except Exception:
        return False
