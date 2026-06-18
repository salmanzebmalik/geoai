import json

import geopandas as gpd


def run_tree_detection(pipeline, image_bytes: bytes, bbox_coords: tuple):
    mask = pipeline.get_full_mask_from_bytes(image_bytes)
    gdf = pipeline.bbox_to_tree_geojson(bbox_coords, mask)

    if isinstance(gdf, gpd.GeoDataFrame):
        return json.loads(gdf.to_json())

    return gdf


def run_zero_shot_detection(
    pipeline,
    image_bytes: bytes,
    bbox_coords: tuple,
    keyword: str = "tree",
):
    
    mask = pipeline.get_full_mask_from_bytes(
        image_bytes,
        keyword=keyword,
    )

    gdf = pipeline.bbox_to_tree_geojson(bbox_coords, mask, keyword)

    if isinstance(gdf, gpd.GeoDataFrame):
        return json.loads(gdf.to_json())

    
    return gdf