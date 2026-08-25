from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ML_SERVICE_DIR = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = ML_SERVICE_DIR.parent
ENV_FILE = ML_SERVICE_DIR / ".env"
DEFAULT_SHARED_STORAGE = REPOSITORY_ROOT / "storage"


class Settings(BaseSettings):
    shared_storage_dir: str = str(DEFAULT_SHARED_STORAGE)

    max_concurrent_inferences: int = Field(default=1, ge=1)
    busy_retry_after_seconds: int = Field(default=30, ge=1)

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()


def get_shared_storage_path() -> Path:
    return Path(settings.shared_storage_dir).resolve()