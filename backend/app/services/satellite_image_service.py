from pathlib import Path
from urllib.parse import urlencode

import requests
from PIL import Image

from app.core.config import settings
from app.schemas.segmentation import BoundingBox, ImageInfo, SourceType


def get_shared_storage_dir() -> Path:
    """
    Return shared storage root.

    This directory must be visible to both:
    - backend service
    - ML service
    """
    path = settings.shared_storage_path
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_query_dir(query_id: str) -> Path:
    query_dir = get_shared_storage_dir() / "queries" / str(query_id)
    query_dir.mkdir(parents=True, exist_ok=True)
    return query_dir


def get_input_image_path(query_id: str) -> Path:
    return get_query_dir(query_id) / "input.tiff"


def bbox_to_titiler_string(bbox: BoundingBox) -> str:
    return f"{bbox.min_lon},{bbox.min_lat},{bbox.max_lon},{bbox.max_lat}"


def build_titiler_request(
    bbox: BoundingBox,
    source_type: SourceType = "satellite",
) -> tuple[str, dict]:
    bbox_string = bbox_to_titiler_string(bbox)

    if source_type == "satellite":
        endpoint = f"{settings.titiler_base_url}/cog/bbox/{bbox_string}.tif"
        params = {
            "url": settings.satellite_vrt_path,
            "bidx": [3, 2, 1],
            "rescale": "0,3000",
        }
        return endpoint, params

    if source_type == "ortho":
        endpoint = f"{settings.titiler_base_url}/mosaicjson/bbox/{bbox_string}.tif"
        params = {
            "url": settings.ortho_mosaic_path,
        }
        return endpoint, params

    raise ValueError("Invalid source_type. Use 'satellite' or 'ortho'.")


def fetch_satellite_image_from_titiler(
    query_id: str,
    bbox: BoundingBox,
    source_type: SourceType = "satellite",
) -> tuple[str, ImageInfo]:
    """
    Fetch cropped image from tiTiler and save it into shared storage.

    Output:
        storage/queries/{query_id}/input.tiff
    """

    image_path = get_input_image_path(query_id)

    endpoint, params = build_titiler_request(
        bbox=bbox,
        source_type=source_type,
    )

    request_url = endpoint + "?" + urlencode(params, doseq=True)

    print("\n========== tiTiler Request Debug ==========")
    print("URL:", request_url)
    print("Source type:", source_type)
    print("Shared storage root:", get_shared_storage_dir())
    print("Output image path:", image_path)
    print("==========================================\n")

    session = requests.Session()
    session.trust_env = False

    try:
        response = session.get(request_url)

        print("\n========== tiTiler Response Debug ==========")
        print("Status code:", response.status_code)
        print("Content-Type:", response.headers.get("content-type"))
        print("Content-Length:", response.headers.get("content-length"))
        print("Final URL:", response.url)
        print("===========================================\n")

        response.raise_for_status()

    except requests.exceptions.ConnectionError as e:
        raise RuntimeError(
            f"Could not connect to tiTiler at {settings.titiler_base_url}: {e}"
        ) from e

    except requests.exceptions.Timeout as e:
        raise RuntimeError(
            f"tiTiler request timed out: {request_url}"
        ) from e

    except requests.exceptions.HTTPError as e:
        raise RuntimeError(
            f"tiTiler returned HTTP {response.status_code}: {response.text[:1000]}"
        ) from e

    except requests.exceptions.RequestException as e:
        raise RuntimeError(
            f"Failed to call tiTiler: {e}"
        ) from e

    if not response.content:
        raise RuntimeError("tiTiler returned an empty image.")

    image_path.parent.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(response.content)

    try:
        with Image.open(image_path) as img:
            width, height = img.width, img.height

    except Exception as e:
        raise RuntimeError(
            f"Image was saved but could not be opened: {image_path}. Error: {e}"
        ) from e

    image_info = ImageInfo(
        image_url=str(image_path),
        width=width,
        height=height,
        format="tiff",
    )

    return str(image_path), image_info