from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Required — service crashes at startup if not provided (no hard-coded fallback).
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # PostgreSQL (falls back to SQLite for bare local dev)
    DATABASE_URL: str = "sqlite:////app/data/auth.db"

    # Redis — if set, refresh tokens and rate-limit counters are stored here
    REDIS_URL: str = ""

    # Google OAuth2 — leave blank to skip audience validation in dev
    GOOGLE_CLIENT_ID: str = ""

    # Base URL used in password-reset emails
    FRONTEND_URL: str = "http://localhost:3000"

    # Comma-separated origin allowlist for CORS. Use "*" only for dev.
    CORS_ALLOWED_ORIGINS: str = "http://localhost:8081,http://localhost:19006,http://localhost:3000"

    # SendGrid — leave blank to skip email sending (dev / test environments)
    SENDGRID_API_KEY: str = ""
    SENDGRID_FROM_EMAIL: str = "noreply@sleepsense.app"

    # Analytics service internal URL — used to purge user data on account deletion
    ANALYTICS_SERVICE_URL: str = "http://localhost:8002"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
