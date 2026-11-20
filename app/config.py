import os
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", "")

    APP_ENV: str = os.getenv("APP_ENV", "development")
    APP_DEBUG: bool = os.getenv("APP_DEBUG", "true").lower() == "true"
    APP_SECRET_KEY: str = os.getenv("APP_SECRET_KEY", "smarttimetable_secret_2026")

    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")

    BOOTSTRAP_OFFICER_ID: str = os.getenv("BOOTSTRAP_OFFICER_ID", "17301")
    BOOTSTRAP_OFFICER_TEMP_PASSWORD: str = os.getenv("BOOTSTRAP_OFFICER_TEMP_PASSWORD", "8296060284")

    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    PORT: int = int(os.getenv("PORT", "8000"))
    HOST: str = os.getenv("HOST", "0.0.0.0")

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
