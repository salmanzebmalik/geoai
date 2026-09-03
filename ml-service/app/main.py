from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import asynccontextmanager
import sys
import threading
import time
from fastapi import FastAPI
from app.api.router import api_router
from app.utils.logger import get_logger
from app.core.config import settings
from app.services.inference_gate import InferenceGate

# Consts & inits
logger = get_logger(__name__)
MODEL_NAMES = ["segformer", "lang_sam_large", "lang_sam_tiny", "satlas_tree", "unet_tree", "deepforest"]
OFFLINE = True

def _load_all(app: FastAPI) -> None:
    t0 = time.time()

    import torch

    if torch.cuda.is_available():
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True
        logger.info(f"cuda: {torch.cuda.get_device_name(0)} | tf32 on")

    # Imports sequential´ly to avoid deadlocks when loading models in parallel
    from app.models.tree_pipeline import TCDSegformer
    from app.models.sam_pipeline import LangSAMPipeline
    from app.models.satlas_tree_pipeline import SatlasTreePipeline
    from app.models.unet_tree_pipeline import UNetTreePipeline
    from app.models.deepforest_pipeline import DeepForestPipeline
    from app.models.yolo11_pipeline import YOLO11Pipeline

    logger.info(f"imports done at {time.time() - t0:.1f}s")

    # Loads weights paralelly
    model_mapping = {
        "deepforest":  lambda: DeepForestPipeline(),
        "lang_sam_large": lambda: LangSAMPipeline(
            patch_size=1024,
            overlap=64,
            offline=OFFLINE,
            text_threshold=0.2,
            box_threshold=0.3,
            variant="sam2.1_hiera_large",
            batch_size=2
        ),
        "segformer":   lambda: TCDSegformer(offline=OFFLINE, patch_size=1024, overlap=128, batch_size=8),
        "satlas_tree": lambda: SatlasTreePipeline(patch_size=512, overlap=64),
        "unet_tree":   lambda: UNetTreePipeline(),
        "yolo11":      lambda: YOLO11Pipeline(),
    }

    with ThreadPoolExecutor(max_workers=len(model_mapping), thread_name_prefix="load") as pool:
        futures = {pool.submit(fn): name for name, fn in model_mapping.items()}
        for fut in as_completed(futures):
            name = futures[fut]
            try:
                app.state.models[name] = fut.result()
                logger.info(f"{name} ready:   {time.time() - t0:.1f}s")
            except Exception:
                logger.exception(f"{name} failed to load")

    large = app.state.models.get("lang_sam_large")
    if large is not None:
        try:
            app.state.models["lang_sam_tiny"] = LangSAMPipeline(
                patch_size=1024,
                overlap=64,
                offline=OFFLINE,
                text_threshold=0.2,
                box_threshold=0.3,
                variant="sam2.1_hiera_tiny",
                batch_size=2,
                share_gdino_from=large,
            )
            logger.info(f"lang_sam_tiny ready:   {time.time() - t0:.1f}s")
        except Exception:
            logger.exception("lang_sam_tiny failed to load")

    logger.info(f"all models loaded in {time.time()-t0:.1f}s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.inference_gate = InferenceGate(
        settings.max_concurrent_inferences
    )

    logger.info(
        "GPU inference admission capacity: "
        f"{settings.max_concurrent_inferences}"
    )

    app.state.models = {n: None for n in MODEL_NAMES}
    threading.Thread(
        target=_load_all,
        args=(app,),
        name="loader",
        daemon=True,
    ).start()

    logger.info("ML service up - models loading in background")
    yield

    torch = sys.modules.get("torch")
    if torch is not None and torch.cuda.is_available():
        torch.cuda.synchronize()
        torch.cuda.empty_cache()


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
    return {
        "status": "healthy",
        "loaded": {
            name: model is not None
            for name, model in app.state.models.items()
        },
        "admission": app.state.inference_gate.snapshot(),
    }


app.include_router(api_router, prefix="/api/v1")