from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


ML_SERVICE_DIR = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = ML_SERVICE_DIR.parent
ENV_FILE = ML_SERVICE_DIR / ".env"
DEFAULT_SHARED_STORAGE = REPOSITORY_ROOT / "storage"


class Settings(BaseSettings):
    shared_storage_dir: str = str(DEFAULT_SHARED_STORAGE)

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()


def get_shared_storage_path() -> Path:
    return Path(settings.shared_storage_dir).resolve()