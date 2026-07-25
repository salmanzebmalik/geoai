import time

import numpy as np
import rasterio
from rasterio.windows import Window

from app.utils.logger import get_logger

logger = get_logger(__name__)


def read_rgb(src, window=None) -> np.ndarray:
    """Bands 1-3 as (H, W, 3) uint8."""
    img = np.moveaxis(src.read([1, 2, 3], window=window), 0, -1)
    if img.dtype == np.uint16:
        img = (img >> 8).astype(np.uint8)
    return np.ascontiguousarray(img)


def tiled_mask(image_bytes: bytes, patch_size: int, overlap: int,
               predict, label: str = "") -> np.ndarray:
    """predict(patch_hwc_uint8) -> (th, tw) bool array"""
    stride = patch_size - overlap
    t0 = time.time()

    with rasterio.MemoryFile(image_bytes) as mem, mem.open() as src:
        h, w = src.height, src.width
        full = np.zeros((h, w), dtype=bool)
        tiles = [(x, y) for y in range(0, h, stride) for x in range(0, w, stride)]
        logger.info(f"{label} | {h}x{w} | {len(tiles)} tiles")

        done = failed = 0
        for x, y in tiles:
            th, tw = min(patch_size, h - y), min(patch_size, w - x)
            try:
                mask = predict(read_rgb(src, Window(x, y, tw, th)))
                if mask is not None:
                    full[y:y + th, x:x + tw] |= np.asarray(mask).astype(bool)
                done += 1
            except Exception as e:
                failed += 1
                logger.warning(f"{label} tile ({x},{y}) failed: {e}")

    logger.info(f"{label} | {done}/{len(tiles)} tiles | {failed} failed | {time.time() - t0:.1f}s")
    return full.astype(np.uint8)