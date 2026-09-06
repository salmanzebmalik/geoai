"""Build a mosaicJSON (v0.0.3) from a list of raster files."""

import json
import math
from pathlib import Path

import mercantile
import rasterio
from rasterio.warp import transform_bounds


def build_mosaic(files, out_path, name=None, quadkey_zoom=12, minzoom=8, maxzoom=None):
    """Write a mosaicJSON covering `files` to `out_path` and return it.

    The first file in `files` wins for overlapping tiles (titiler's default
    pixel_selection=first), so list the preferred / newest source first.
    """
    per_file = []
    native_max = 0
    for p in files:
        with rasterio.open(p) as ds:
            wgs = transform_bounds(ds.crs, "EPSG:4326", *ds.bounds)
            merc = transform_bounds(ds.crs, "EPSG:3857", *ds.bounds)
            res_m = (merc[2] - merc[0]) / ds.width
        per_file.append((p, wgs))
        native_max = max(native_max, int(round(math.log2(156543.0339280410 / res_m))))

    if maxzoom is None:
        maxzoom = min(22, native_max)

    w = min(b[0] for _, b in per_file)
    s = min(b[1] for _, b in per_file)
    e = max(b[2] for _, b in per_file)
    n = max(b[3] for _, b in per_file)

    order = {p: i for i, p in enumerate(files)}
    tiles = {}
    eps = 1e-9
    for path, (fw, fs, fe, fn) in per_file:
        for t in mercantile.tiles(fw, fs, fe - eps, fn - eps, [quadkey_zoom]):
            tiles.setdefault(mercantile.quadkey(t), []).append(path)
    for qk in tiles:
        tiles[qk].sort(key=lambda p: order[p])

    out_path = Path(out_path)
    mosaic = {
        "mosaicjson": "0.0.3",
        "name": name or out_path.stem,
        "version": "1.0.0",
        "minzoom": minzoom,
        "maxzoom": maxzoom,
        "quadkey_zoom": quadkey_zoom,
        "bounds": [w, s, e, n],
        "center": [(w + e) / 2, (s + n) / 2, minzoom],
        "tiles": tiles,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(mosaic, indent=2))
    return mosaic
