from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
from uuid import uuid4
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from app.inference import run_tree_detection, run_zero_shot_detection
from app.schemas import PredictionResponse, GeoJSONFeatureCollection
import torch


UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Model already initialized in inference.py => subject to change

    yield
    # on shutdown, clean pytorch resources
    if torch.cuda.is_available():
        torch.cuda.synchronize()
        torch.cuda.empty_cache()

    # to prevent leaked semaphore warning
    shutdown_fn = getattr(torch.multiprocessing, "_shutdown", None)
    if shutdown_fn is not None:
        try:
            shutdown_fn()
        except Exception:
            pass


app = FastAPI(
    title="GeoAI ML Service",
    description="ML service for building footprint prediction from satellite imagery.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/")
def root():
    return {"message": "GeoAI ML Service is running"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.post("/predict", response_model=PredictionResponse)
async def predict_building_footprints(
    image: UploadFile = File(...),
    query_id: str = Form(default=None),
    min_lon: float = Form(...),
    min_lat: float = Form(...),
    max_lon: float = Form(...),
    max_lat: float = Form(...),
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

    if image.filename:
        file_extension = Path(image.filename).suffix.lower()
    else:
        raise HTTPException(status_code=400, detail="...")

    if file_extension not in allowed_extensions:
        raise HTTPException(status_code=400, detail="Uploaded image must be a .tif, .tiff or .jp2 file")

    image_bytes = await image.read()
    if len(image_bytes) == 0:
        raise HTTPException(400, "Empty file")

    # bbox = (min_lon, min_lat, max_lon, max_lat)
    bbox = (7.68, 51.99, 7.685, 52)
    try:
        geojson_dict = run_tree_detection(image_bytes, bbox)
        feature_collection = GeoJSONFeatureCollection(**geojson_dict)
        return PredictionResponse(
            query_id=str(uuid4()),
            status="completed",
            model_name="tcd-segformer-mit-b2",
            prediction_type="tree_detection",
            geojson=feature_collection,
            summary=f"Found {len(feature_collection.features)} tree poylgons/clusters",
        )

    except Exception as e:
        raise HTTPException(500, f"inference failed --- error: {str(e)}")


@app.post("/predict/zeroshot")
async def detect_zeroshot(
    image: UploadFile = File(...),
    min_lon: float = Form(...),
    min_lat: float = Form(...),
    max_lon: float = Form(...),
    max_lat: float = Form(...),
    keyword: str = Form(default="solar panel"),
):

    image_bytes = await image.read()
    # bbox = (min_lon, min_lat, max_lon, max_lat)
    bbox = (7.68, 51.99, 7.685, 52)
    try:
        geojson_dict = run_zero_shot_detection(image_bytes, bbox, keyword=keyword)
        feature_collection = GeoJSONFeatureCollection(**geojson_dict)
        return PredictionResponse(
            query_id=str(uuid4()),
            status="completed",
            model_name="lang-sam",
            prediction_type="zero_shot_detection",
            geojson=feature_collection,
            summary=f"Found {len(feature_collection.features)} {keyword} polygons/clusters",
        )

    except Exception as e:
        raise HTTPException(500, f"inference failed --- error: {str(e)}")
