from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    SECRET_KEY: str = "sleepsense-dev-secret-key-32chars!!"
    ALGORITHM: str = "HS256"

    # PostgreSQL (falls back to SQLite for bare local dev)
    DATABASE_URL: str = "sqlite:////app/data/analytics.db"

    # Redis
    REDIS_URL: str = ""

    # InfluxDB — snore event time-series
    INFLUXDB_URL: str = ""
    INFLUXDB_TOKEN: str = "dev-influxdb-token-sleepsense-2024"
    INFLUXDB_ORG: str = "sleepsense"
    INFLUXDB_BUCKET: str = "snore_events"

    # Kafka — async event bus
    KAFKA_BOOTSTRAP_SERVERS: str = ""  # e.g. "kafka:9092"

    # MinIO / S3 — audio file storage
    MINIO_ENDPOINT: str = ""
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "audio-chunks"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
