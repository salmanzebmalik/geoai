import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()



REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


class Settings:
    # -----------------------------
    # App
    # -----------------------------
    app_title: str = "GeoAI Segmentation Backend API"
    app_description: str = "Backend API for bounding-box based satellite image segmentation."
    app_version: str = "1.0.0"

    # -----------------------------
    # CORS
    # -----------------------------
    cors_origins: list[str] = [
        origin.strip()
        for origin in os.getenv(
            "BACKEND_CORS_ORIGINS",
            # Added more ports just temporarily 
            "http://localhost:3000,http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174,http://localhost:5175,http://127.0.0.1:5175" 
            
        ).split(",")
        if origin.strip()
    ]


    cors_origin_regex: str = os.getenv(
        "BACKEND_CORS_ORIGIN_REGEX",
        r"http://(localhost|127\.0\.0\.1):(517[3-9]|518[0-9])$",
    )

    # -----------------------------
    # External services
    # -----------------------------
    # dev ports: 8000-8003 are taken by the production stack (see PORTS.md), so use 801x
    ml_service_url: str = os.getenv(
        "ML_SERVICE_URL",
        "http://127.0.0.1:8012",
    ).rstrip("/")

    titiler_base_url: str = os.getenv(
        "TITILER_BASE_URL",
        "http://127.0.0.1:8011",
    ).rstrip("/")

    # -----------------------------
    # Shared storage
    # -----------------------------
    shared_storage_dir: str = os.getenv(
        "SHARED_STORAGE_DIR",
        str(REPOSITORY_ROOT / "storage"),
    )

    # -----------------------------
    # Raster sources
    # -----------------------------
    satellite_vrt_path: str = os.getenv(
        "SATELLITE_VRT_PATH",
        "/home/ubuntu/work/satellite_data/germany/2021/2021_08.vrt",
    )

    ortho_mosaic_path: str = os.getenv(
        "ORTHO_MOSAIC_PATH",
        "/home/ubuntu/work/saved_data/collections/digital_orthofoto_nrw/mosaic.json",
    )

    # -----------------------------
    # Database
    # -----------------------------
    database_echo: bool = os.getenv("DATABASE_ECHO", "false").lower() == "true"

    @property
    def database_url(self) -> str:
        """
        Prefer DATABASE_URL if available.
        Otherwise build the URL from individual env variables.
        """

        direct_url = os.getenv("DATABASE_URL")
        if direct_url:
            return direct_url

        user = os.getenv("POSTGRES_USER") or os.getenv("user")
        password = os.getenv("POSTGRES_PASSWORD") or os.getenv("password")
        host = os.getenv("POSTGRES_HOST") or os.getenv("host")
        port = os.getenv("POSTGRES_PORT") or os.getenv("port")
        dbname = os.getenv("POSTGRES_DB") or os.getenv("dbname")
        sslmode = os.getenv("POSTGRES_SSLMODE", "require")

        missing = [
            name
            for name, value in {
                "user/POSTGRES_USER": user,
                "password/POSTGRES_PASSWORD": password,
                "host/POSTGRES_HOST": host,
                "port/POSTGRES_PORT": port,
                "dbname/POSTGRES_DB": dbname,
            }.items()
            if not value
        ]

        if missing:
            raise RuntimeError(
                "Database configuration is incomplete. Missing: "
                + ", ".join(missing)
            )

        return (
            f"postgresql+psycopg2://{user}:{password}"
            f"@{host}:{port}/{dbname}?sslmode={sslmode}"
        )

    @property
    def shared_storage_path(self) -> Path:
        return Path(self.shared_storage_dir).resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()