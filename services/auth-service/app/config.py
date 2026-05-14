from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    SECRET_KEY: str = "sleepsense-dev-secret-key-32chars!!"
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

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
