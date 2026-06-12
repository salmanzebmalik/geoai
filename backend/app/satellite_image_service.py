from pathlib import Path
from urllib.parse import urlencode

import requests
from PIL import Image

from app.schemas import BoundingBox, ImageInfo

# Import your config/settings
# Adjust this import if your config file has a different location/name
from app.core.config import settings


# -----------------------------
# tiTiler service URL
# -----------------------------
TITILER_BASE_URL = "http://localhost:8001"

# Raster sources
SATELLITE_VRT_PATH = "/home/ubuntu/work/satellite_data/germany/2021/2021_08.vrt"
ORTHO_MOSAIC_PATH = "/home/ubuntu/work/saved_data/collections/digital_orthofoto_nrw/mosaic.json"


# -----------------------------
# Shared storage helpers
# -----------------------------
def get_shared_storage_dir() -> Path:
    """
    Return the shared storage root directory.

    Example:
        /home/ubuntu/your-project/storage
        or
        /app/storage inside Docker
    """
    return Path(settings.shared_storage_dir).resolve()


def get_query_dir(query_id: str) -> Path:
    """
    Return query-specific storage folder.

    Example:
        storage/queries/{query_id}
    """
    query_dir = get_shared_storage_dir() / "queries" / str(query_id)
    query_dir.mkdir(parents=True, exist_ok=True)
    return query_dir


def get_input_image_path(query_id: str) -> Path:
    """
    Return full path for the input image.

    Example:
        storage/queries/{query_id}/input.tiff
    """
    return get_query_dir(query_id) / "input.tiff"


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

    The image is saved into shared storage:

        storage/queries/{query_id}/input.tiff

    Args:
        query_id: Unique query ID for the query folder.
        bbox: Bounding box coordinates.
        source_type: "satellite" for VRT imagery, "ortho" for MosaicJSON.

    Returns:
        Tuple containing:
        - Local shared-storage path to saved TIFF image
        - ImageInfo object with image path, width, height, format
    """

    image_path = get_input_image_path(query_id)
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
        params = {
            "url": ORTHO_MOSAIC_PATH,
        }

    else:
        raise ValueError("Invalid source_type. Use 'satellite' or 'ortho'.")

    request_url = endpoint + "?" + urlencode(params, doseq=True)

    print("\n========== tiTiler Request Debug ==========")
    print("Request URL:", request_url)
    print("Bounding box string:", bbox_string)
    print("Params:", params)
    print("Shared storage root:", get_shared_storage_dir())
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
        raise RuntimeError(
            f"tiTiler request timed out: {request_url}"
        ) from e

    except requests.exceptions.RequestException as e:
        raise RuntimeError(
            f"Failed to call tiTiler: {e}"
        ) from e

    # -----------------------------
    # Check response
    # -----------------------------
    if response.status_code != 200:
        raise RuntimeError(
            f"tiTiler request failed with status {response.status_code}.\n"
            f"URL: {request_url}\nResponse: {response.text[:1000]}"
        )

    # -----------------------------
    # Save image into shared storage
    # -----------------------------
    image_path.parent.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(response.content)

    # -----------------------------
    # Read image dimensions
    # -----------------------------
    with Image.open(image_path) as img:
        width, height = img.width, img.height

    image_info = ImageInfo(
        # This is no longer a public static URL.
        # It is now the internal shared-storage path.
        image_url=str(image_path),
        width=width,
        height=height,
        format="tiff",
    )

    return str(image_path), image_info