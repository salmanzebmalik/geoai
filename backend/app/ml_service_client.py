import os
from pathlib import Path

import requests
from dotenv import load_dotenv
from app.schemas import BoundingBox, ImageInfo

load_dotenv()

ML_SERVICE_URL = os.getenv("ML_SERVICE_URL", "http:127.0.0.1:8000")


def call_ml_service(
    image_path: str,
    query_id: str,
) -> dict:
    """
    Sends a TIFF image to the ML service and receives GeoJSON building footprints.

    The ML service is expected to expose:
        POST /predict

    With multipart form data:
        image: .tif/.tiff file
        query_id: string
    """

    predict_url = f"{ML_SERVICE_URL}/predict"

    image_file_path = Path(image_path)

    if not image_file_path.exists():
        raise FileNotFoundError(f"Image file not found: {image_path}")

    with image_file_path.open("rb") as image_file:
        files = {
            "image": (
                image_file_path.name,
                image_file,
                "image/tiff",
            )
        }

        data = {
            "query_id": query_id
        }

        response = requests.post(
            predict_url,
            files=files,
            data=data,
            timeout=60,
        )

    response.raise_for_status()

    return response.json()


def call_ml_service_dummy(query_id: str, bbox: BoundingBox) -> dict:
    """
    Sends a form-encoded POST request to the ML service with bounding box.
    """
    url = f"{ML_SERVICE_URL}/predict"
    data = {
        "query_id": query_id,
        "min_lon": bbox.min_lon,
        "min_lat": bbox.min_lat,
        "max_lon": bbox.max_lon,
        "max_lat": bbox.max_lat,
    }

    session = requests.Session()
    session.trust_env = False  # important to bypass proxy settings
    
    try:
        response = session.post(
            url,
            data=data,
            headers={"Accept": "application/json"},
            timeout=60,
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"ML service request failed: {e}") from e

    try:
        return response.json()
    except ValueError:
        raise RuntimeError(f"ML service returned invalid JSON: {response.text[:500]}")