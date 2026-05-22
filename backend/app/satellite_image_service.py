from pathlib import Path
from typing import Tuple

from PIL import Image, ImageDraw

from app.schemas import BoundingBox, ImageInfo


STATIC_DIR = Path("static")
IMAGE_DIR = STATIC_DIR / "images"

IMAGE_WIDTH = 512
IMAGE_HEIGHT = 512


def ensure_image_folder_exists() -> None:
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)


def fetch_satellite_image_placeholder(
    query_id: str,
    bbox: BoundingBox,
) -> tuple[str, ImageInfo]:
    """
    Placeholder service for satellite image fetching.

    Current behavior:
    - Creates a dummy .tiff image.
    - Saves it inside backend/static/images.
    - Returns the local image path and image metadata.

    Future behavior:
    - Use bbox coordinates to fetch/crop a real satellite image.
    - Save the real GeoTIFF.
    - Return its path and metadata.
    """

    ensure_image_folder_exists()

    image_path = IMAGE_DIR / f"{query_id}.tiff"

    image = Image.new("RGB", (IMAGE_WIDTH, IMAGE_HEIGHT), color=(90, 130, 90))
    draw = ImageDraw.Draw(image)

    # Dummy vegetation-like background
    draw.rectangle([0, 0, 260, 512], fill=(70, 140, 70))

    # Dummy building-like objects
    draw.rectangle([80, 80, 150, 150], fill=(180, 180, 180))
    draw.rectangle([170, 90, 250, 170], fill=(170, 170, 170))
    draw.rectangle([100, 230, 210, 330], fill=(190, 190, 190))
    draw.rectangle([280, 280, 390, 390], fill=(175, 175, 175))

    # Dummy road-like lines
    draw.line([0, 420, 512, 420], fill=(110, 110, 110), width=35)
    draw.line([300, 0, 300, 512], fill=(100, 100, 100), width=30)

    image.save(image_path, format="TIFF")

    image_info = ImageInfo(
        image_url=f"/static/images/{query_id}.tiff",
        width=IMAGE_WIDTH,
        height=IMAGE_HEIGHT,
        format="tiff",
    )

    return str(image_path), image_info