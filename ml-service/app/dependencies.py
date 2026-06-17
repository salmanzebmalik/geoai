from fastapi import Request


def get_segformer_model(request: Request):
    return request.app.state.models["segformer"]


def get_lang_sam_model(request: Request):
    return request.app.state.models["lang_sam"]