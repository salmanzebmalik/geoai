from fastapi import APIRouter

from app.api.endpoints import segmentation


api_router = APIRouter()

api_router.include_router(
    segmentation.router,
    prefix="/segmentation",
    tags=["segmentation prediction"],
)