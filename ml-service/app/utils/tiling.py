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
               predict, label: str = "", batch_size: int = 1) -> np.ndarray:
    """predict(list of (th, tw, 3) uint8 patches) """
    stride = patch_size - overlap
    t0 = time.time()

    with rasterio.MemoryFile(image_bytes) as mem, mem.open() as src:
        h, w = src.height, src.width
        full = np.zeros((h, w), dtype=bool)
        tiles = [(x, y) for y in range(0, h, stride) for x in range(0, w, stride)]
        logger.info(f"{label} | {h}x{w} | {len(tiles)} tiles | batch {batch_size}")

        by_shape: dict[tuple[int, int], list[tuple[int, int]]] = {}
        for x, y in tiles:
            shape = (min(patch_size, h - y), min(patch_size, w - x))
            by_shape.setdefault(shape, []).append((x, y))

        done = failed = skipped = 0
        for (th, tw), coords in by_shape.items():
            for start in range(0, len(coords), batch_size):
                chunk = coords[start:start + batch_size]
                try:
                    read = [(xy, read_rgb(src, Window(xy[0], xy[1], tw, th))) for xy in chunk]
                    kept = [(xy, patch) for xy, patch in read if patch.any()]
                    skipped += len(read) - len(kept)
                    if not kept:
                        continue

                    masks = predict([patch for _, patch in kept])
                    for ((x, y), _), mask in zip(kept, masks):
                        if mask is not None:
                            full[y:y + th, x:x + tw] |= np.asarray(mask).astype(bool)
                    done += len(kept)
                except Exception as e:
                    failed += len(chunk)
                    logger.warning(f"{label} batch at {chunk[0]} ({th}x{tw}) failed: {e}")

    logger.info(f"{label} | {done}/{len(tiles)} tiles | {skipped} empty | {failed} failed | {time.time() - t0:.1f}s")
    return full.astype(np.uint8)