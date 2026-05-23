import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from app.inference import run_dummy_building_footprint_prediction, run_tree_detection
from app.schemas import PredictionResponse, GeoJSONFeatureCollection


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
    min_lon: float = Form(...),
    min_lat: float = Form(...),
    max_lon: float = Form(...),
    max_lat: float = Form(...)
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

    allowed_extensions = [".tif", ".tiff", ".jp2"]

    file_extension = Path(image.filename).suffix.lower()

    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail="Uploaded image must be a .tif, .tiff or .jp2 file"
        )
    
    image_bytes = await image.read()
    if len(image_bytes) == 0:
        raise HTTPException(400, "Empty file")

    bbox = (min_lon, min_lat, max_lon, max_lat)
    try:
        geojson_dict = run_tree_detection(image_bytes, bbox)
        feature_collection = GeoJSONFeatureCollection(**geojson_dict)
        return PredictionResponse(
            query_id=str(uuid4()),
            status="completed",
            model_name="tcd-segformer-mit-b2",
            prediction_type="tree_detection",
            geojson=feature_collection,
            summary=f"Found {len(feature_collection.features)} tree poylgons/clusters"
        )

    except Exception as e:
        raise HTTPException(500, f"inference failed --- error: {str(e)}")
