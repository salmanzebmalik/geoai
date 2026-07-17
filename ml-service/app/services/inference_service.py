import json
import time

from app.utils.instancing import mask_to_instances, instances_to_geojson
from app.utils.logger import get_logger
logger = get_logger(__name__)


# ----- Instance segmentation related parameters --------
# False = connected-component "blobs" 
# True  = watershed instances 
SPLIT_TOUCHING = False


def _mask_to_geojson(mask, bbox_coords: tuple, keyword: str) -> dict:
    labels = mask_to_instances(mask, split_touching=SPLIT_TOUCHING, min_area=0)
    gdf = instances_to_geojson(labels, bbox_coords, class_name=keyword)
    return json.loads(gdf.to_json())


def run_tree_detection(pipeline, image_bytes: bytes, bbox_coords: tuple):
    start_time = time.time()
    mask = pipeline.get_full_mask_from_bytes(image_bytes)
    result = _mask_to_geojson(mask, bbox_coords, "tree")
    logger.info(f"Tree detection complete | {len(result['features'])} features | {time.time() - start_time:.2f}s")
    return result


def run_zero_shot_detection(pipeline, image_bytes: bytes, bbox_coords: tuple, keyword: str = "tree"):
    start_time = time.time()
    mask = pipeline.get_full_mask_from_bytes(image_bytes, keyword=keyword)
    result = _mask_to_geojson(mask, bbox_coords, keyword)
    logger.info(f"Zero-shot detection complete | {len(result['features'])} {keyword} features | {time.time() - start_time:.2f}s")
    return result
