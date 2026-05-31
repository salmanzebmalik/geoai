from app.models.tree_pipeline import TCDSegformer
from app.models.sam_pipeline import LangSAMPipeline
import geopandas as gpd
import json


_pipeline = TCDSegformer()
langsam_detector = LangSAMPipeline(patch_size=1024,  overlap=128)


# TODO: add model as parameter to select between different tree detection models?
def run_tree_detection(image_bytes: bytes, bbox_coords: tuple):
    mask = _pipeline.get_full_mask_from_bytes(image_bytes)
    gdf = _pipeline.bbox_to_tree_geojson(bbox_coords, mask)
    if isinstance(gdf, gpd.GeoDataFrame):
        return json.loads(gdf.to_json())
    return gdf


# TODO: add model as parameter to select between different zero-shot models?
def run_zero_shot_detection(image_bytes: bytes, bbox_coords: tuple, keyword: str = "Solar Panel"):
    mask = langsam_detector.get_full_mask_from_bytes(image_bytes, keyword=keyword)
    gdf = langsam_detector.bbox_to_tree_geojson(bbox_coords, mask)
    if isinstance(gdf, gpd.GeoDataFrame):
        return json.loads(gdf.to_json())
    return gdf
