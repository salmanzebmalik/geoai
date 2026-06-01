import os
from pathlib import Path

import requests
from dotenv import load_dotenv


load_dotenv()

ML_SERVICE_URL = os.getenv("ML_SERVICE_URL", "http://127.0.0.1:8001")


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