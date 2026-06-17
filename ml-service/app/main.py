from contextlib import asynccontextmanager

import torch
from fastapi import FastAPI

from app.api.router import api_router
from app.models.tree_pipeline import TCDSegformer
from app.models.sam_pipeline import LangSAMPipeline


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Loading models...")

    try:
        offline = False

        app.state.models = {
            "segformer": TCDSegformer(offline=offline),
            "lang_sam": LangSAMPipeline(
                patch_size=1024,
                overlap=128,
                offline=offline,
            ),
        }

        print("Models loaded successfully")

    except Exception as e:
        print(f"Failed to load models: {e}")
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