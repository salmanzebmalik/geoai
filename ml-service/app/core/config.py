from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    shared_storage_dir: str = "/home/ubuntu/work/saved_data/salman/geoai/storage"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()


def get_shared_storage_path() -> Path:
    return Path(settings.shared_storage_dir).resolve()