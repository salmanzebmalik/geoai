from fastapi import HTTPException, Request


def get_segformer_model(request: Request):
    return request.app.state.models["segformer"]


def get_lang_sam_model(request: Request):
    return request.app.state.models["lang_sam"]


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