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
