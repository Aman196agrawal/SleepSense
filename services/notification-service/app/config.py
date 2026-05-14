from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    SECRET_KEY: str = "sleepsense-dev-secret-key-32chars!!"
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

    # Kafka
    KAFKA_BOOTSTRAP_SERVERS: str = ""
    KAFKA_GROUP_ID: str = "notification-service"
    KAFKA_SESSION_ENDED_TOPIC: str = "session.ended"
    KAFKA_NOTIFICATION_TOPIC: str = "notification.send"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
