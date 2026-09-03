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
        "http://127.0.0.1:8041",
    ).rstrip("/")

    # -----------------------------
    # Internal HTTP communication
    # -----------------------------
    titiler_connect_timeout_seconds: float = float(
        os.getenv("TITILER_CONNECT_TIMEOUT_SECONDS", "5")
    )

    titiler_read_timeout_seconds: float = float(
        os.getenv("TITILER_READ_TIMEOUT_SECONDS", "300")
    )

    ml_connect_timeout_seconds: float = float(
        os.getenv("ML_CONNECT_TIMEOUT_SECONDS", "5")
    )

    ml_read_timeout_seconds: float = float(
        os.getenv("ML_READ_TIMEOUT_SECONDS", "1800")
    )
    
    # -----------------------------
    # Input raster safety limits
    # -----------------------------
    ortho_resolution_meters_per_pixel: float = float(
        os.getenv("ORTHO_RESOLUTION_METERS_PER_PIXEL", "0.10")
    )

    satellite_resolution_meters_per_pixel: float = float(
        os.getenv("SATELLITE_RESOLUTION_METERS_PER_PIXEL", "3.0")
    )

    sentinel_resolution_meters_per_pixel: float = float(
        os.getenv("SENTINEL_RESOLUTION_METERS_PER_PIXEL", "10.0")
    )

    raster_estimate_margin: float = float(
        os.getenv("RASTER_ESTIMATE_MARGIN", "1.10")
    )

    max_input_raster_pixels: int = int(
        os.getenv("MAX_INPUT_RASTER_PIXELS", "25000000")
    )

    max_input_raster_side_pixels: int = int(
        os.getenv("MAX_INPUT_RASTER_SIDE_PIXELS", "8000")
    )
    
    # Tested specifically with: source_type="ortho", model_type="tree"
    max_ortho_raster_pixels: int = int(
        os.getenv(
            "MAX_ORTHO_RASTER_PIXELS",
            "210000000",
        )
    )

    max_ortho_raster_side_pixels: int = int(
        os.getenv(
            "MAX_ORTHO_RASTER_SIDE_PIXELS",
            "18000",
        )
    )
    
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

    # --- Sentinel-2 via STAC --------------------------------------------------
    # Unlike the satellite/ortho sources above, this is not a fixed file path:
    # titiler resolves the imagery through a pgstac search, so the crop can be
    # filtered by date and cloud cover.
    #
    # These are the jp2-de-<year> collections: raw 16-bit L2A bands restricted to
    # the German tiles, with REAL valid-data footprints. Do NOT point this at
    # sentinel-2-l2a-worldwide-<year>: those items advertise the full MGRS tile
    # outline, so pgstac's skipcovered shortcut stops early on a partial granule
    # and the crop comes back entirely black (verified over the area north of
    # Plzen: worldwide mean 0.0, jp2-de mean 140.1 for the same bbox).
    sentinel_collections: list[str] = (
        os.getenv(
            "SENTINEL_COLLECTIONS",
            ",".join(f"sentinel-2-l2a-jp2-de-{y}" for y in range(2018, 2025)),
        ).split(",")
    )
    # Growing season by default: wide enough that every tile has a qualifying
    # scene, and it keeps cloud-ordering from reaching into snowy winter scenes.
    sentinel_date_from: str = os.getenv("SENTINEL_DATE_FROM", "2024-04-01")
    sentinel_date_to: str = os.getenv("SENTINEL_DATE_TO", "2024-09-30")
    sentinel_max_cloud_cover: float = float(os.getenv("SENTINEL_MAX_CLOUD_COVER", "30"))

    # -----------------------------
    # Prediction concurrency
    # -----------------------------
    max_concurrent_predictions: int = int(
        os.getenv("MAX_CONCURRENT_PREDICTIONS", "1")
    )

    prediction_busy_retry_after_seconds: int = int(
        os.getenv(
            "PREDICTION_BUSY_RETRY_AFTER_SECONDS",
            "30",
        )
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