from pathlib import Path
from typing import Literal, Optional
from urllib import response

import requests

from app.core.config import settings
from app.utils.http import get_http_session

ModelType = Literal["tree", "tree_satlas", "tree_unet", "tree_deepforest", "zeroshot"]

ML_ENDPOINTS = {
    "tree": "/api/v1/predict/tree",                      # TCD-Segformer, 10cm ortho
    "tree_satlas": "/api/v1/predict/tree/satlas",        # Satlas, 5m satellite
    "tree_unet": "/api/v1/predict/tree/unet",            # UNet, 5m satellite
    "tree_deepforest": "/api/v1/predict/tree/deepforest",  # DeepForest boxes, 10cm ortho
    "zeroshot": "/api/v1/predict/zeroshot",
}

DEFAULT_BUSY_RETRY_AFTER_SECONDS = 30


class MLServiceBusyError(RuntimeError):
    def __init__(self, retry_after_seconds: int):
        self.retry_after_seconds = retry_after_seconds

        super().__init__(
            "GPU inference capacity is currently full. "
            "Please retry later."
        )


def _parse_retry_after_seconds(value: str | None) -> int:
    if value is None:
        return DEFAULT_BUSY_RETRY_AFTER_SECONDS

    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return DEFAULT_BUSY_RETRY_AFTER_SECONDS

def get_ml_endpoint(model_type: ModelType) -> str:
    try:
        return ML_ENDPOINTS[model_type]
    except KeyError:
        raise ValueError(f"Unsupported model_type: {model_type}")

def get_shared_storage_relative_path(path: str | Path) -> str:
    """
    Convert an absolute shared-storage path into a storage-relative path.

    Example:
        /server/storage/queries/123/input.tiff
    becomes:
        queries/123/input.tiff
    """

    storage_root = settings.shared_storage_path
    resolved_path = Path(path).resolve()

    try:
        relative_path = resolved_path.relative_to(storage_root)
    except ValueError as e:
        raise ValueError(
            f"Path is outside shared storage: {resolved_path}"
        ) from e

    return relative_path.as_posix()

def call_ml_service(
    query_id: str,
    input_image_path: str,
    model_type: ModelType = "tree",
    keyword: Optional[str] = None,
) -> dict:
    """
    Call the ML service using the shared-storage image path.

    The ML service georeferences the prediction from the input GeoTIFF's own
    CRS/bounds, so no bounding box is sent.

    Backend sends:
        query_id
        input_image_path
        output_dir
        optional keyword for zero-shot
    """

    endpoint = get_ml_endpoint(model_type)
    url = f"{settings.ml_service_url}{endpoint}"

    relative_input_image_path = get_shared_storage_relative_path(
        input_image_path
    )

    output_dir = Path(relative_input_image_path).parent.as_posix()

    payload = {
        "query_id": query_id,
        "input_image_path": relative_input_image_path,
        "output_dir": output_dir,
    }

    if model_type == "zeroshot":
        payload["keyword"] = keyword or "tree"

    session = get_http_session()

    print("\n========== ML Service Request Debug ==========")
    print("URL:", url)
    print("Model type:", model_type)
    print("Payload:", payload)
    print("=============================================\n")

    try:
        
        response = session.post(
            url,
            json=payload,
            headers={"Accept": "application/json"},
            timeout=(
                settings.ml_connect_timeout_seconds,
                settings.ml_read_timeout_seconds,
            ),
        )

        print("\n========== ML Service Response Debug ==========")
        print("Status code:", response.status_code)
        print("Content-Type:", response.headers.get("content-type"))
        print("Response preview:", response.text[:500])
        print("==============================================\n")

        if response.status_code == 429:
            raise MLServiceBusyError(
                retry_after_seconds=_parse_retry_after_seconds(
                    response.headers.get("Retry-After")
                )
            )

        response.raise_for_status()

    except requests.exceptions.ConnectionError as e:
        raise RuntimeError(
            f"Could not connect to ML service at {settings.ml_service_url}: {e}"
        ) from e

    except requests.exceptions.Timeout as e:
        raise RuntimeError(
            "ML service request timed out "
            f"(connect={settings.ml_connect_timeout_seconds}s, "
            f"read={settings.ml_read_timeout_seconds}s): "
            f"{url}"
        ) from e

    except requests.exceptions.HTTPError as e:
        raise RuntimeError(
            f"ML service returned HTTP {response.status_code}: {response.text[:1000]}"
        ) from e

    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"ML service request failed: {e}") from e

    try:
        return response.json()
    except ValueError as e:
        raise RuntimeError(
            f"ML service returned invalid JSON: {response.text[:1000]}"
        ) from e