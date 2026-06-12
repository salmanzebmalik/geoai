import os
from pathlib import Path

import requests
from dotenv import load_dotenv
from app.schemas import BoundingBox, ImageInfo

load_dotenv()

ML_SERVICE_URL = os.getenv("ML_SERVICE_URL", "http:127.0.0.1:8000")


def call_ml_service(query_id: str, bbox: BoundingBox, input_image_path: str,) -> dict:
    """
    Sends a form-encoded POST request to the ML service with bounding box.
    """
    url = f"{ML_SERVICE_URL}/predict"
    output_dir = str(Path(input_image_path).parent)
    data = {
        "query_id": query_id,
        "input_image_path": input_image_path,
        "output_dir": output_dir,
        "min_lon": bbox.min_lon,
        "min_lat": bbox.min_lat,
        "max_lon": bbox.max_lon,
        "max_lat": bbox.max_lat,
    }

    session = requests.Session()
    session.trust_env = False  # important to bypass proxy settings
    
    print("\n========== ML Service Request Debug ==========")
    print("ML Service URL:", f"{ML_SERVICE_URL}/predict")
    print("Data:", data)
    print("=============================================\n")
    
    try:
        response = session.post(
            url,
            json=data,
            headers={"Accept": "application/json"},
            timeout=300,
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"ML service request failed: {e}") from e

    try:
        return response.json()
    except ValueError:
        raise RuntimeError(f"ML service returned invalid JSON: {response.text[:500]}")