from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
from uuid import uuid4
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from app.inference import run_tree_detection, run_zero_shot_detection
from app.schemas import PredictionResponse, GeoJSONFeatureCollection
import torch
import requests
from pydantic import BaseModel

from app.core.config import get_shared_storage_path
from app.utils.storage import ensure_path_inside_storage

from app.models.tree_pipeline import TCDSegformer
from app.models.sam_pipeline import LangSAMPipeline

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Loading models...")
    try:
        offline = False  # use HF weight loading by default
        app.state.segformer = TCDSegformer(offline=offline)
        app.state.lang_sam = LangSAMPipeline(patch_size=1024, overlap=128, offline=offline)
        print("Models loaded successfully")
    except Exception as e:
        print(f"Failed to load models: {e}")
        raise

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


class PredictionRequest(BaseModel):
    query_id: str | None = None
    input_image_path: str
    output_dir: str | None = None

    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float


@app.post("/predict", response_model=PredictionResponse)
async def predict_footprints(request: PredictionRequest):

    if request.query_id is None:
        query_id = str(uuid4())
    else:
        query_id = request.query_id

    print('ML Service: Running Query for: ', query_id)

    storage_root = get_shared_storage_path()

    try:
        input_path = ensure_path_inside_storage(
            request.input_image_path,
            storage_root,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not input_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Input image not found: {input_path}",
        )

    if not input_path.is_file():
        raise HTTPException(
            status_code=400,
            detail=f"Input path is not a file: {input_path}",
        )

    # -----------------------------
    # Optional: validate/create output dir
    # -----------------------------
    output_dir = None

    if request.output_dir is not None:
        try:
            output_dir = ensure_path_inside_storage(
                request.output_dir,
                storage_root,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        output_dir.mkdir(parents=True, exist_ok=True)

    # -----------------------------
    # Read image bytes from shared storage
    # -----------------------------
    try:
        image_bytes = input_path.read_bytes()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read input image from shared storage: {str(e)}",
        )

    if len(image_bytes) == 0:
        raise HTTPException(
            status_code=400,
            detail="Input image exists but is empty.",
        )

    bbox = (
        request.min_lon,
        request.min_lat,
        request.max_lon,
        request.max_lat,
    )

    # -----------------------------
    # Run model inference
    # -----------------------------
    try:
        segformer = app.state.segformer
        geojson_dict = run_tree_detection(segformer, image_bytes, bbox)
        feature_collection = GeoJSONFeatureCollection(**geojson_dict)

        return PredictionResponse(
            query_id=query_id,
            status="completed",
            model_name="tcd-segformer-mit-b2",
            prediction_type="tree_detection",
            geojson=feature_collection,
            summary=f"Found {len(feature_collection.features)} tree polygons/clusters",
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Inference failed --- error: {str(e)}",
        )


@app.post("/predict/zeroshot")
async def detect_zeroshot(
    query_id: str = Form(default=None),
    min_lon: float = Form(...),
    min_lat: float = Form(...),
    max_lon: float = Form(...),
    max_lat: float = Form(...),
    keyword: str = Form(default="tree"),
):

    if query_id is None:
        query_id = str(uuid4())

    titiler_url = f"http://127.0.0.1:8001/cog/bbox/{min_lon},{min_lat},{max_lon},{max_lat}.tif"

    proxies = {
        "http": None,
        "https": None,
    }
    params = {
        "url": "/home/ubuntu/work/satellite_data/germany/2021/2021_08.vrt",
        "bidx": [3, 2, 1],  # RGB bands
        "rescale": "0,3000"
    }

    # fetch the image from Titiler
    try:
        response = requests.get(titiler_url, params=params, proxies=proxies, timeout=30)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise HTTPException(
            status_code=503 if isinstance(e, requests.exceptions.ConnectionError) else 500,
            detail=f"Failed to fetch image from titiler: {str(e)}"
        )

    image_bytes = response.content
    if len(image_bytes) == 0:
        raise HTTPException(400, "titiler returned an empty image")

    bbox = (min_lon, min_lat, max_lon, max_lat)
    try:
        geojson_dict = run_zero_shot_detection(image_bytes, bbox, keyword=keyword)
        feature_collection = GeoJSONFeatureCollection(**geojson_dict)
        return PredictionResponse(
            query_id=query_id,
            status="completed",
            model_name="lang-sam",
            prediction_type="zero_shot_detection",
            geojson=feature_collection,
            summary=f"Found {len(feature_collection.features)} {keyword} polygons/clusters",
        )

    except Exception as e:
        raise HTTPException(500, f"inference failed --- error: {str(e)}")
