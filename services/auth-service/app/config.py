from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    SECRET_KEY: str = "product-gem-dev-secret-key-32chars!!"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # PostgreSQL (falls back to SQLite for bare local dev)
    DATABASE_URL: str = "sqlite:////app/data/auth.db"

    # Redis — if set, refresh tokens are stored here instead of PostgreSQL
    REDIS_URL: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
