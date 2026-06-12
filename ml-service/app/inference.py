from app.models.tree_pipeline import TCDSegformer
from app.models.sam_pipeline import LangSAMPipeline
import geopandas as gpd
import json


def run_tree_detection(pipeline, image_bytes: bytes, bbox_coords: tuple):
    mask = pipeline.get_full_mask_from_bytes(image_bytes)
    gdf = pipeline.bbox_to_tree_geojson(bbox_coords, mask)
    if isinstance(gdf, gpd.GeoDataFrame):
        return json.loads(gdf.to_json())
    return gdf


def run_zero_shot_detection(pipeline, image_bytes: bytes, bbox_coords: tuple, keyword: str = "Solar Panel"):
    mask = pipeline.get_full_mask_from_bytes(image_bytes, keyword=keyword)
    gdf = pipeline.bbox_to_tree_geojson(bbox_coords, mask)
    if isinstance(gdf, gpd.GeoDataFrame):
        return json.loads(gdf.to_json())
    return gdf
