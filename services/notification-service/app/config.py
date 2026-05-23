from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Required — service crashes at startup if not provided (no hard-coded fallback).
    SECRET_KEY: str
    ALGORITHM: str = "HS256"

    DATABASE_URL: str = "sqlite:////app/data/notifications.db"

    # FCM (Android push) — leave blank to use stub
    FCM_SERVER_KEY: str = ""

    # APNs (iOS push) — leave blank to use stub
    APNS_KEY_ID: str = ""
    APNS_TEAM_ID: str = ""
    APNS_KEY_FILE: str = ""
    APNS_TOPIC: str = "com.sleepsense.app"

    # SendGrid — leave blank to use stub
    SENDGRID_API_KEY: str = ""
    SENDGRID_FROM_EMAIL: str = "noreply@sleepsense.app"
    SENDGRID_FROM_NAME: str = "SleepSense"

    # Auth service internal URL — used for bedtime reminder lookups
    AUTH_SERVICE_URL: str = "http://localhost:8001"

    # Kafka
    KAFKA_BOOTSTRAP_SERVERS: str = ""
    KAFKA_GROUP_ID: str = "notification-service"
    KAFKA_SESSION_ENDED_TOPIC: str = "session.ended"
    KAFKA_NOTIFICATION_TOPIC: str = "notification.send"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
