import json
import time

import geopandas as gpd
from app.utils.logger import get_logger
logger = get_logger(__name__)

def run_tree_detection(pipeline, image_bytes: bytes, bbox_coords: tuple):
    logger.info("Starting tree detection")
    start_time = time.time()
    mask = pipeline.get_full_mask_from_bytes(image_bytes)
    gdf = pipeline.bbox_to_tree_geojson(bbox_coords, mask)

    if isinstance(gdf, gpd.GeoDataFrame):
        elapsed = time.time() - start_time
        logger.info(f"Tree detection complete | {len(gdf)} trees | {elapsed:.2f}s")
        return json.loads(gdf.to_json())

    logger.warning("Unexpected return type from pipeline")
    return gdf


def run_zero_shot_detection(
    pipeline,
    image_bytes: bytes,
    bbox_coords: tuple,
    keyword: str = "tree",
):
    
    logger.info(f"Starting zero-shot detection | keyword: '{keyword}'")
    start_time = time.time()

    mask = pipeline.get_full_mask_from_bytes(
        image_bytes,
        keyword=keyword,
    )

    gdf = pipeline.bbox_to_tree_geojson(bbox_coords, mask, keyword)

    if isinstance(gdf, gpd.GeoDataFrame):
        elapsed = time.time() - start_time
        logger.info(f"Zero-shot detection complete | {len(gdf)} {keyword}s | {elapsed:.2f}s")
        return json.loads(gdf.to_json())
    logger.warning("Unexpected return type from pipeline")
    return gdf