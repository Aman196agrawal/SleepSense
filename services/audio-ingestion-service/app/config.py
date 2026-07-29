from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./data/ingestion.db"
    # Required — service crashes at startup if not provided (no hard-coded fallback).
    SECRET_KEY: str

    # Where chunk audio is stored.
    #   "s3"    — S3 or MinIO via boto3 (production, and docker-compose locally)
    #   "local" — plain files under AUDIO_STORAGE_DIR, the same trade auth and
    #             analytics make by using SQLite instead of Postgres for local
    #             dev. Avoids needing Docker/MinIO just to keep audio.
    AUDIO_STORAGE_BACKEND: str = "s3"
    AUDIO_STORAGE_DIR: str = "./data/audio"

    # S3 / MinIO
    # Must match the bucket minio-init creates in docker-compose.yml; the old
    # default ("sleepsense-audio-dev") existed nowhere and every upload 404'd
    # when the service ran outside compose.
    S3_BUCKET: str = "audio-chunks"
    S3_ENDPOINT_URL: str = ""          # blank = real AWS; set to MinIO URL for local dev
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_REGION: str = "ap-south-1"

    # Kafka
    KAFKA_BOOTSTRAP_SERVERS: str = ""

    # Shared secret for internal service-to-service calls
    INTERNAL_API_SECRET: str = ""

    # Redis
    REDIS_URL: str = ""

    # Limits
    MAX_CHUNK_SIZE_MB: int = 10
    CHUNK_RATE_LIMIT_PER_HOUR: int = 120
    UPLOAD_TOKEN_TTL_HOURS: int = 8

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
