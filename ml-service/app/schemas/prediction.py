from pydantic import BaseModel

from app.schemas.geojson import GeoJSONFeatureCollection


class BasePredictionRequest(BaseModel):
    query_id: str | None = None
    input_image_path: str
    output_dir: str | None = None
    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float


class TreePredictionRequest(BasePredictionRequest):
    pass


class ZeroShotPredictionRequest(BasePredictionRequest):
    keyword: str = "tree"


class PredictionResponse(BaseModel):
    query_id: str
    status: str
    model_name: str
    prediction_type: str
    geojson: GeoJSONFeatureCollection
    summary: str