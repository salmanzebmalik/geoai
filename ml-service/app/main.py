from contextlib import asynccontextmanager

import torch
from fastapi import FastAPI

from app.api.router import api_router
from app.models.tree_pipeline import TCDSegformer
from app.models.sam_pipeline import LangSAMPipeline
from app.models.satlas_tree_pipeline import SatlasTreePipeline

from app.utils.logger import get_logger
logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up ML service and loading models...")

    try:
        offline = True  # set to True to load from local files, False to load from Hugging Face 

        app.state.models = {
            "segformer": TCDSegformer(
                offline=offline, 
                patch_size=1024, 
                overlap=128
                ),
            "lang_sam": LangSAMPipeline(
                patch_size=1024,
                overlap=128,
                offline=offline,
            ),
        }

        # satellite (~5m) tree model — weights come from satlas_tree_5m.ipynb, optional
        try:
            app.state.models["satlas_tree"] = SatlasTreePipeline(patch_size=512, overlap=64)
        except FileNotFoundError as e:
            app.state.models["satlas_tree"] = None
            logger.warning(f"Satlas tree model not loaded: {e}")

        logger.info("Models loaded successfully")

    except Exception as e:
        logger.error(f"Error loading models: {e}")
        raise

    yield

    if torch.cuda.is_available():
        torch.cuda.synchronize()
        torch.cuda.empty_cache()

    shutdown_fn = getattr(torch.multiprocessing, "_shutdown", None)
    if shutdown_fn is not None:
        try:
            shutdown_fn()
        except Exception:
            pass


app = FastAPI(
    title="GeoAI ML Service",
    description="ML service for geospatial object detection from satellite imagery.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/")
def root():
    return {"message": "GeoAI ML Service is running"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}


app.include_router(api_router, prefix="/api/v1")