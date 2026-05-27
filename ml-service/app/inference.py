from app.models.tree_pipeline import InferencePipeline
import geopandas as gpd
import json


_pipeline = InferencePipeline()


# Tree detection
def run_tree_detection_test(image_path: str, bbox_coords: tuple):
    mask = _pipeline.get_full_mask(image_path)
    gdf = _pipeline.bbox_to_tree_geojson(bbox_coords, mask)
    if isinstance(gdf, gpd.GeoDataFrame):
        return json.loads(gdf.to_json())
    return gdf


def run_tree_detection(image_bytes: bytes, bbox_coords: tuple):
    mask = _pipeline.get_full_mask_from_bytes(image_bytes)
    gdf = _pipeline.bbox_to_tree_geojson(bbox_coords, mask)
    if isinstance(gdf, gpd.GeoDataFrame):
        return json.loads(gdf.to_json())
    return gdf
