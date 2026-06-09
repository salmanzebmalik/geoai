# backend/app/core/config.py

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    shared_storage_dir: str = "storage"
    ml_service_url: str = "http://localhost:8002"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()


def get_shared_storage_path() -> Path:
    return Path(settings.shared_storage_dir).resolve()