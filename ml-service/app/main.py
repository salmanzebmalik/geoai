from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import asynccontextmanager
import sys
import threading
import time
from fastapi import FastAPI
from app.api.router import api_router
from app.utils.logger import get_logger

# Consts & inits
logger = get_logger(__name__)
MODEL_NAMES = ["segformer", "lang_sam", "satlas_tree", "unet_tree", "deepforest"]
OFFLINE = True

def _load_all(app: FastAPI) -> None:
    t0 = time.time()

    # Imports sequential´ly to avoid deadlocks when loading models in parallel
    from app.models.tree_pipeline import TCDSegformer
    from app.models.sam_pipeline import LangSAMPipeline
    from app.models.satlas_tree_pipeline import SatlasTreePipeline
    from app.models.unet_tree_pipeline import UNetTreePipeline
    from app.models.deepforest_pipeline import DeepForestPipeline

    logger.info(f"imports done at {time.time() - t0:.1f}s")

    # Loads weights paralelly
    model_mapping = {
        "deepforest":  lambda: DeepForestPipeline(),
        "lang_sam":    lambda: LangSAMPipeline(patch_size=1024, overlap=128, offline=OFFLINE,text_threshold=0.2, box_threshold=0.3),
        "segformer":   lambda: TCDSegformer(offline=OFFLINE, patch_size=1024, overlap=128),
        "satlas_tree": lambda: SatlasTreePipeline(patch_size=512, overlap=64),
        "unet_tree":   lambda: UNetTreePipeline(),
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

    logger.info(f"all models loaded in {time.time()-t0:.1f}s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.models = {n: None for n in MODEL_NAMES}
    threading.Thread(target=_load_all, args=(app,), name="loader", daemon=True).start()
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
        "loaded": {n: m is not None for n, m in app.state.models.items()},
    }


app.include_router(api_router, prefix="/api/v1")