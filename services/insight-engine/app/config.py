from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    SECRET_KEY: str = "sleepsense-dev-secret-key-32chars!!"
    ALGORITHM: str = "HS256"

    DATABASE_URL: str = "sqlite:////app/data/insights.db"

    # Kafka
    KAFKA_BOOTSTRAP_SERVERS: str = ""
    KAFKA_GROUP_ID: str = "insight-engine"
    KAFKA_INPUT_TOPIC: str = "insights.generate"
    KAFKA_NOTIFICATION_TOPIC: str = "notification.send"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
