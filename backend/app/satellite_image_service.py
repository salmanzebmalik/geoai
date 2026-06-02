from pathlib import Path
from urllib.parse import urlencode

import requests
from PIL import Image

from app.schemas import BoundingBox, ImageInfo

# -----------------------------
# Config
# -----------------------------
STATIC_DIR = Path("static")
IMAGE_DIR = STATIC_DIR / "images"

# tiTiler service URL (running on VM)
TITILER_BASE_URL = "http://localhost:8001"

# Raster sources
SATELLITE_VRT_PATH = "/home/ubuntu/work/satellite_data/germany/2021/2021_08.vrt"
ORTHO_MOSAIC_PATH = "/home/ubuntu/work/saved_data/collections/digital_orthofoto_nrw/mosaic.json"


# -----------------------------
# Helpers
# -----------------------------
def ensure_image_folder_exists() -> None:
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)


def bbox_to_titiler_string(bbox: BoundingBox) -> str:
    """
    Convert BoundingBox to tiTiler bbox format:
        min_lon,min_lat,max_lon,max_lat
    """
    return f"{bbox.min_lon},{bbox.min_lat},{bbox.max_lon},{bbox.max_lat}"


# -----------------------------
# Main function
# -----------------------------
def fetch_satellite_image_from_titiler(
    query_id: str,
    bbox: BoundingBox,
    source_type: str = "satellite",
) -> tuple[str, ImageInfo]:
    """
    Fetch a cropped satellite or orthophoto image from tiTiler.

    Args:
        query_id: Unique query ID for naming the image file.
        bbox: Bounding box coordinates.
        source_type: "satellite" for VRT imagery, "ortho" for MosaicJSON.

    Returns:
        Tuple containing:
        - Local path to saved TIFF image
        - ImageInfo object with URL, width, height, format
    """
    ensure_image_folder_exists()
    image_path = IMAGE_DIR / f"{query_id}.tiff"

    bbox_string = bbox_to_titiler_string(bbox)

    if source_type == "satellite":
        endpoint = f"{TITILER_BASE_URL}/cog/bbox/{bbox_string}.tif"
        params = {
            "url": SATELLITE_VRT_PATH,
            "bidx": [3, 2, 1],
            "rescale": "0,3000",
        }
    elif source_type == "ortho":
        endpoint = f"{TITILER_BASE_URL}/mosaicjson/bbox/{bbox_string}.tif"
        params = {"url": ORTHO_MOSAIC_PATH}
    else:
        raise ValueError("Invalid source_type. Use 'satellite' or 'ortho'.")

    request_url = endpoint + "?" + urlencode(params, doseq=True)

    print("\n========== tiTiler Request Debug ==========")
    print("Request URL:", request_url)
    print("Bounding box string:", bbox_string)
    print("Params:", params)
    print("Output image path:", image_path)
    print("==========================================\n")

    # -----------------------------
    # Request the image from tiTiler
    # -----------------------------
    try:
        session = requests.Session()
        session.trust_env = False  # avoid proxies

        response = session.get(request_url, timeout=60)

        print("\n========== tiTiler Response Debug ==========")
        print("Status code:", response.status_code)
        print("Content-Type:", response.headers.get("content-type"))
        print("Content-Length:", response.headers.get("content-length"))
        print("Final URL:", response.url)
        print("===========================================\n")

    except requests.exceptions.ConnectionError as e:
        raise RuntimeError(
            f"Could not connect to tiTiler at {TITILER_BASE_URL}: {e}"
        ) from e
    except requests.exceptions.Timeout as e:
        raise RuntimeError(f"tiTiler request timed out: {request_url}") from e
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Failed to call tiTiler: {e}") from e

    # -----------------------------
    # Check response
    # -----------------------------
    if response.status_code != 200:
        raise RuntimeError(
            f"tiTiler request failed with status {response.status_code}.\n"
            f"URL: {request_url}\nResponse: {response.text[:1000]}"
        )

    # -----------------------------
    # Save image
    # -----------------------------
    image_path.write_bytes(response.content)

    # Read image to get dimensions
    with Image.open(image_path) as img:
        width, height = img.width, img.height

    image_info = ImageInfo(
        image_url=f"/static/images/{query_id}.tiff",
        width=width,
        height=height,
        format="tiff",
    )

    return str(image_path), image_info