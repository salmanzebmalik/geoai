from fastapi import APIRouter

from app.api.endpoints import tree_detection, zero_shot


api_router = APIRouter()

api_router.include_router(
    tree_detection.router,
    prefix="/predict",
    tags=["Tree Detection"],
)

api_router.include_router(
    zero_shot.router,
    prefix="/predict",
    tags=["Zero-Shot Detection"],
)