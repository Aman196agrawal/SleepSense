from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Required — service crashes at startup if not provided (no hard-coded fallback).
    SECRET_KEY: str
    ALGORITHM: str = "HS256"

    # PostgreSQL (falls back to SQLite for bare local dev)
    DATABASE_URL: str = "sqlite:////app/data/analytics.db"

    # Redis
    REDIS_URL: str = ""

    # Auth-service base URL used for the inter-service user-existence check.
    AUTH_SERVICE_URL: str = ""

    # InfluxDB — snore event time-series. Token is required when INFLUXDB_URL is set.
    INFLUXDB_URL: str = ""
    INFLUXDB_TOKEN: str = ""
    INFLUXDB_ORG: str = "sleepsense"
    INFLUXDB_BUCKET: str = "snore_events"

    # Kafka — async event bus
    KAFKA_BOOTSTRAP_SERVERS: str = ""  # e.g. "kafka:9092"
    KAFKA_GROUP_ID:          str = "analytics-consumer-group"

    # S3 / MinIO — audio file storage (used for pre-signed playback URLs, FR-VIS-002)
    S3_BUCKET: str = ""                 # blank → audio playback unavailable
    S3_ENDPOINT_URL: str = ""           # blank = real AWS; set to MinIO URL for local dev
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_REGION: str = "ap-south-1"

    # Comma-separated origin allowlist for CORS. Use "*" only for dev.
    CORS_ALLOWED_ORIGINS: str = "http://localhost:8081,http://localhost:19006,http://localhost:3000"

    # Shared secret for service-to-service internal endpoints
    INTERNAL_API_SECRET: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

# Fail fast: if Influx is configured but no token was supplied, refuse to start
# rather than running with a publicly-known default.
if settings.INFLUXDB_URL and not settings.INFLUXDB_TOKEN:
    raise RuntimeError(
        "INFLUXDB_TOKEN must be set when INFLUXDB_URL is configured. "
        "Refusing to start with a missing token."
    )
