import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from app.inference import run_dummy_building_footprint_prediction
from app.schemas import PredictionResponse


UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


app = FastAPI(
    title="GeoAI ML Service",
    description="ML service for building footprint prediction from satellite imagery.",
    version="0.1.0",
)


@app.get("/")
def root():
    return {
        "message": "GeoAI ML Service is running"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }


@app.post("/predict", response_model=PredictionResponse)
async def predict_building_footprints(
    image: UploadFile = File(...),
    query_id: str = Form(default=None),
):
    """
    Receive a satellite image and return building footprint polygons.

    Current version:
    - receives .tif/.tiff image
    - saves it temporarily
    - returns dummy GeoJSON polygons

    Future version:
    - loads the .tiff image
    - runs trained building segmentation model
    - converts model output to vector polygons
    - returns GeoJSON
    """

    if query_id is None:
        query_id = str(uuid4())

    allowed_extensions = [".tif", ".tiff"]

    file_extension = Path(image.filename).suffix.lower()

    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail="Uploaded image must be a .tif or .tiff file."
        )

    image_path = UPLOAD_DIR / f"{query_id}_{image.filename}"

    try:
        with image_path.open("wb") as buffer:
            shutil.copyfileobj(image.file, buffer)

        geojson_result = run_dummy_building_footprint_prediction()

        return PredictionResponse(
            query_id=query_id,
            status="completed",
            model_name="dummy_building_footprint_model",
            prediction_type="building_footprint_geojson",
            geojson=geojson_result,
            summary="Dummy building footprint polygons generated successfully."
        )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"ML prediction failed: {str(error)}"
        )