import logging
from app.config import settings

_logger = logging.getLogger(__name__)


def download_audio(s3_key: str) -> bytes:
    """Download audio bytes from S3. Returns empty bytes if unavailable."""
    try:
        import boto3
        client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL or None,
            aws_access_key_id=settings.S3_ACCESS_KEY or None,
            aws_secret_access_key=settings.S3_SECRET_KEY or None,
            region_name=settings.S3_REGION,
        )
        resp = client.get_object(Bucket=settings.S3_BUCKET, Key=s3_key)
        return resp["Body"].read()
    except Exception as exc:
        _logger.error("S3 download failed for %s: %s", s3_key, exc)
        return b""
