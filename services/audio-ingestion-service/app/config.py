from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./data/ingestion.db"
    SECRET_KEY: str = "dev-secret-key-change-in-production"

    # S3 / MinIO
    S3_BUCKET: str = "sleepsense-audio-dev"
    S3_ENDPOINT_URL: str = ""          # blank = real AWS; set to MinIO URL for local dev
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_REGION: str = "ap-south-1"

    # Kafka
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"

    # Redis
    REDIS_URL: str = ""

    # Limits
    MAX_CHUNK_SIZE_MB: int = 10
    CHUNK_RATE_LIMIT_PER_HOUR: int = 120
    UPLOAD_TOKEN_TTL_HOURS: int = 8

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
