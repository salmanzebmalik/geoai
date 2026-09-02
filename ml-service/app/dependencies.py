from fastapi import HTTPException, Request

from collections.abc import Iterator

from fastapi import HTTPException, Request

from app.core.config import settings

def get_segformer_model(request: Request):
    model = request.app.state.models.get("segformer")
    if model is None:
        raise HTTPException(503, "Segformer still loading")
    return model


def get_lang_sam_models(request: Request):
    return {
        "sam2.1_hiera_large": request.app.state.models.get("lang_sam_large"),
        "sam2.1_hiera_tiny": request.app.state.models.get("lang_sam_tiny"),
    }


def get_satlas_tree_model(request: Request):
    model = request.app.state.models.get("satlas_tree")
    if model is None:
        raise HTTPException(status_code=503, detail="Satellite tree model not trained yet (run satlas_tree_5m.ipynb)")
    return model


def get_unet_tree_model(request: Request):
    model = request.app.state.models.get("unet_tree")
    if model is None:
        raise HTTPException(status_code=503, detail="UNet tree model not trained yet (run tree_crown_5m.ipynb)")
    return model


def get_deepforest_model(request: Request):
    model = request.app.state.models.get("deepforest")
    if model is None:
        raise HTTPException(status_code=503, detail="DeepForest model not available (pip install deepforest)")
    return model

def acquire_inference_slot(request: Request) -> Iterator[None]:
    gate = request.app.state.inference_gate

    if not gate.try_acquire():
        state = gate.snapshot()

        raise HTTPException(
            status_code=429,
            detail=(
                "GPU inference capacity is currently full. "
                f"{state['active']} of {state['capacity']} "
                "slot(s) are active. Retry later."
            ),
            headers={
                "Retry-After": str(settings.busy_retry_after_seconds),
            },
        )

    try:
        yield
    finally:
        gate.release()