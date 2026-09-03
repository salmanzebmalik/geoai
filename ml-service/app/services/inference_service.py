import json
import time

import rasterio

from app.utils.instancing import mask_to_instances, instances_to_geojson
from app.utils.logger import get_logger
logger = get_logger(__name__)


# ----- Instance segmentation related parameters --------
# False = connected-component "blobs" 
# True  = watershed instances 
SPLIT_TOUCHING = False

# Drop instances smaller than 1m squared 
MIN_AREA_M2 = 1.0

def _min_area_px(mask_shape, bounds) -> int:
    h, w = mask_shape
    pixel_area = ((bounds.right - bounds.left) / w) * ((bounds.top - bounds.bottom) / h)
    if pixel_area <= 0:
        return 0
    return int(MIN_AREA_M2 / pixel_area)


def read_georeference(image_bytes: bytes):
    """Bounds + CRS of the input crop, as written by tiTiler.

    The mask comes back on the same pixel grid as the raster, so these place every
    instance without ever going through the request's lon/lat bbox.
    """
    with rasterio.MemoryFile(image_bytes) as memfile:
        with memfile.open() as src:
            if src.crs is None:
                raise ValueError("Input image has no CRS; cannot georeference the prediction.")
            return src.bounds, src.crs


def _mask_to_geojson(mask, bounds, crs, keyword: str) -> dict:
    labels = mask_to_instances(mask, split_touching=SPLIT_TOUCHING,
                               min_area=_min_area_px(mask.shape, bounds)) # ! min area
    gdf = instances_to_geojson(labels, bounds, crs, class_name=keyword)
    return json.loads(gdf.to_json())


def run_tree_detection(pipeline, image_bytes: bytes):
    start_time = time.time()
    bounds, crs = read_georeference(image_bytes)
    mask = pipeline.get_full_mask_from_bytes(image_bytes)
    result = _mask_to_geojson(mask, bounds, crs, "tree")
    logger.info(f"Tree detection complete | {len(result['features'])} features | {crs.to_string()} | {time.time() - start_time:.2f}s")
    return result


def run_zero_shot_detection(pipeline, image_bytes: bytes, keyword: str = "tree"):
    start_time = time.time()
    bounds, crs = read_georeference(image_bytes)
    mask = pipeline.get_full_mask_from_bytes(image_bytes, keyword=keyword)
    result = _mask_to_geojson(mask, bounds, crs, keyword)
    logger.info(f"Zero-shot detection complete | {len(result['features'])} {keyword} features | {crs.to_string()} | {time.time() - start_time:.2f}s")
    return result
