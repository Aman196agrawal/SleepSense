from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    SECRET_KEY: str = "sleepsense-dev-secret-key-32chars!!"

    # PostgreSQL (SQLite fallback for local dev)
    DATABASE_URL: str = "sqlite:///./data/inference.db"

    # InfluxDB
    INFLUXDB_URL:    str = ""
    INFLUXDB_TOKEN:  str = "dev-influxdb-token-sleepsense-2024"
    INFLUXDB_ORG:    str = "sleepsense"
    INFLUXDB_BUCKET: str = "snore_events"

    # Kafka
    KAFKA_BOOTSTRAP_SERVERS: str = ""
    KAFKA_GROUP_ID:          str = "ml-inference-group"
    KAFKA_INPUT_TOPIC:       str = "audio.chunk.uploaded"
    KAFKA_OUTPUT_TOPIC:      str = "analysis.complete"

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
