from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Required — service crashes at startup if not provided (no hard-coded fallback).
    SECRET_KEY: str

    # PostgreSQL (SQLite fallback for local dev)
    DATABASE_URL: str = "sqlite:///./data/inference.db"

    # InfluxDB. Token is required when INFLUXDB_URL is set; no default.
    INFLUXDB_URL:    str = ""
    INFLUXDB_TOKEN:  str = ""
    INFLUXDB_ORG:    str = "sleepsense"
    INFLUXDB_BUCKET: str = "snore_events"

    # Kafka
    KAFKA_BOOTSTRAP_SERVERS: str = ""
    KAFKA_GROUP_ID:          str = "ml-inference-group"
    KAFKA_INPUT_TOPIC:       str = "audio.chunk.uploaded"
    KAFKA_OUTPUT_TOPIC:      str = "analysis.complete"

    # Redis — inference result cache
    REDIS_URL: str = ""

    # S3 / MinIO
    S3_BUCKET:       str = "sleepsense-audio-dev"
    S3_ENDPOINT_URL: str = ""
    S3_ACCESS_KEY:   str = ""
    S3_SECRET_KEY:   str = ""
    S3_REGION:       str = "ap-south-1"

    # Model paths (S3 keys or local paths)
    CLASSIFIER_MODEL_PATH: str = ""   # blank = use stub
    REGRESSOR_MODEL_PATH:  str = ""   # blank = use stub

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
