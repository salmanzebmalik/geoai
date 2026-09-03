from typing import Literal

from pydantic import BaseModel

from app.schemas.geojson import GeoJSONFeatureCollection


class BasePredictionRequest(BaseModel):
    query_id: str | None = None
    input_image_path: str
    output_dir: str | None = None


class TreePredictionRequest(BasePredictionRequest):
    pass


class ZeroShotPredictionRequest(BasePredictionRequest):
    keyword: str = "tree"
    model_variant: Literal["sam2.1_hiera_large", "sam2.1_hiera_tiny"] = "sam2.1_hiera_large"


class PredictionResponse(BaseModel):
    query_id: str
    status: str
    model_name: str
    prediction_type: str
    result_path: str
    feature_count: int
    summary: str