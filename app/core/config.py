from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # App
    app_name: str = "Complaint Management System"
    app_version: str = "0.1.0"
    debug: bool = False

    # MongoDB Atlas
    mongodb_uri: str
    database_name: str = "complaints_db"

    # Session cookie (itsdangerous / Starlette SessionMiddleware)
    secret_key: str = "change-me-in-production"
    session_max_age_seconds: int = 60 * 60 * 24 * 7  # 7 days

    # CORS
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:8000"]

    # AI (optional)
    openai_api_key: str = ""


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()


settings = get_settings()
