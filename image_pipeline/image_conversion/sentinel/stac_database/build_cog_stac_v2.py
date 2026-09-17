#!/usr/bin/env python3
"""
Build a STAC collection for the masked RGB COGs, using the REAL valid-data
footprint as each item's geometry instead of the raster's bounding rectangle.
"""

import argparse
import csv
import warnings
import json
import math
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

warnings.filterwarnings("ignore", category=DeprecationWarning)

import numpy as np
import rasterio
from rasterio import features
from rasterio.enums import MaskFlags
from rasterio.warp import transform_geom
from shapely.geometry import mapping, shape
from shapely.ops import unary_union

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
COG_ROOT_TMPL = "/home/ubuntu/work/saved_data/collections/sentinel_rgb_cogs_v2/{year}"
CSV_DIR = Path("/home/ubuntu/work/saved_data/collections/sentinel")
CSV_TMPL = "links_worldwide_{year}.final.csv"

OUT_ROOT = Path(__file__).resolve().parent / "out"
COLLECTION_TMPL = "sentinel-2-l2a-rgb-cog-v2-{year}"

THREADS = 16
MIN_ASSET_BYTES = 100_000

ASSET_KEY = "visual"
RGB_BANDS = [
    {"name": "B04", "common_name": "red",   "center_wavelength": 0.665},
    {"name": "B03", "common_name": "green", "center_wavelength": 0.560},
    {"name": "B02", "common_name": "blue",  "center_wavelength": 0.490},
]
GSD_M = 10
COG_MEDIA_TYPE = "image/tiff; application=geotiff; profile=cloud-optimized"

# --- footprint derivation ---------------------------------------------------
# The mask is read decimated to roughly this many pixels on the long side. The
# COGs are ~11000 px, so 1024 means ~1/11 decimation: about 170 m per probe
# pixel. That is far finer than the pad wedges we need to exclude (tens of km)
# and keeps polygonisation cheap. Reading a coarser overview would blur the
# swath edge; finer would produce needlessly complex polygons.
PROBE_PX = 1024
# Drop specks: isolated valid blobs smaller than this many probe pixels are
# noise (JPEG-era artefacts, single-pixel mask flecks), not real coverage.
MIN_BLOB_PX = 24
# Simplify tolerance, in probe pixels. Keeps vertex counts sane; 1.5 probe px is
# ~250 m, immaterial for a search geometry.
SIMPLIFY_PX = 1.5
# A FULL granule still measures ~0.95 valid, because the reprojection pad costs
# ~5% of the rectangle. So "partial" has to be judged below that, not below 1.0.
PARTIAL_BELOW = 0.85
# Safety net: if a footprint would still carry more vertices than this after
# simplifying, simplify harder rather than storing a monster in the DB.
MAX_VERTICES = 1500

EO_EXT     = "https://stac-extensions.github.io/eo/v1.1.0/schema.json"
PROJ_EXT   = "https://stac-extensions.github.io/projection/v1.1.0/schema.json"
RASTER_EXT = "https://stac-extensions.github.io/raster/v1.1.0/schema.json"
SAT_EXT    = "https://stac-extensions.github.io/sat/v1.0.0/schema.json"
FILE_EXT   = "https://stac-extensions.github.io/file/v2.1.0/schema.json"
ITEM_ASSETS_EXT = "https://stac-extensions.github.io/item-assets/v1.0.0/schema.json"
RENDER_EXT      = "https://stac-extensions.github.io/render/v2.0.0/schema.json"
ITEM_EXTS = [EO_EXT, PROJ_EXT, RASTER_EXT, SAT_EXT, FILE_EXT]

COG_RE = re.compile(r"^(L2A_(T\w{5})_A(\d+)_(\d{8}T\d{6}))_rgb_3857_cog\.tif$")

T0 = time.time()


def log(msg):
    print(f"[{time.time() - T0:8.1f}s] {msg}", flush=True)


def parse_cog_name(fname):
    m = COG_RE.match(fname)
    if not m:
        return None
    item_id, tile, orbit, stamp = m.group(1), m.group(2), m.group(3), m.group(4)
    d, t = stamp[:8], stamp[9:]
    dt = f"{d[:4]}-{d[4:6]}-{d[6:8]}T{t[:2]}:{t[2:4]}:{t[4:6]}Z"
    day = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
    return item_id, tile, int(orbit), dt, day


def find_cogs(cog_root):
    out = []
    for tile_dir in sorted(p for p in cog_root.iterdir() if p.is_dir()):
        out += sorted(tile_dir.glob("*_rgb_3857_cog.tif"))
    return out


def load_cloud_lookup(csv_path, wanted):
    """(tile, day) -> cloud/area/etc, restricted to keys we need.

    cloudCover in the CSV is a 0-1 FRACTION; eo:cloud_cover is percent.
    Join on the DATE, not the timestamp: the CSV holds the datatake start while
    the filename holds granule sensing time.
    """
    lut = {}
    n_rows = 0
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            n_rows += 1
            if row.get("status", "").strip().lower() != "downloaded":
                continue
            key = (row["tileId"].strip(), row["startDate"].strip()[:10])
            if key not in wanted or key in lut:
                continue

            def num(field):
                try:
                    return float(row[field])
                except (KeyError, TypeError, ValueError):
                    return None

            cloud = num("cloudCover")
            lut[key] = {
                "cloud": round(cloud * 100.0, 4) if cloud is not None else None,
                "area": num("area_covered"),
                "black_area": num("black_area"),
                "baseline": (row.get("processingBaseline") or "").strip() or None,
                "title": (row.get("title") or "").strip() or None,
                "datatake": (row.get("startDate") or "").strip() or None,
            }
    log(f"  CSV: {n_rows} rows scanned, {len(lut)}/{len(wanted)} needed keys resolved")
    return lut


# ---------------------------------------------------------------------------
# the point of this script: geometry from the mask, not from the raster bounds
# ---------------------------------------------------------------------------
def valid_footprint(ds):
    """(geometry_4326, bbox_4326, coverage_fraction) from the internal mask.

    Returns None if no valid pixels were found. `coverage_fraction` is the share
    of the raster rectangle that actually holds data -- 1.0 for a full granule,
    ~0.65 for a typical partial one. It goes into the item as a property so you
    can see at a glance which scenes are partial.
    """
    f = max(1, int(round(max(ds.width, ds.height) / PROBE_PX)))
    h, w = max(1, ds.height // f), max(1, ds.width // f)
    mask = ds.read_masks(1, out_shape=(h, w)).astype(bool)
    frac = float(mask.mean())
    if not mask.any():
        return None

    # transform for the decimated grid
    probe_tf = ds.transform * rasterio.Affine.scale(ds.width / w, ds.height / h)
    px = max(abs(probe_tf.a), abs(probe_tf.e))          # probe pixel size, CRS units

    polys = []
    for geom, val in features.shapes(mask.astype("uint8"), mask=mask, transform=probe_tf):
        if not val:
            continue
        g = shape(geom)
        if g.area < MIN_BLOB_PX * px * px:
            continue
        polys.append(g)
    if not polys:
        return None

    merged = unary_union(polys)
    tol = SIMPLIFY_PX * px
    simple = merged.simplify(tol, preserve_topology=True)
    # keep vertex count bounded
    for _ in range(6):
        n = len(json.dumps(mapping(simple)))
        if _count_vertices(simple) <= MAX_VERTICES:
            break
        tol *= 2
        simple = merged.simplify(tol, preserve_topology=True)
    if simple.is_empty:
        simple = merged
    if not simple.is_valid:
        simple = simple.buffer(0)

    geom4326 = transform_geom(ds.crs, "EPSG:4326", mapping(simple), precision=7)
    g = shape(geom4326)
    if g.is_empty:
        return None
    bbox = [float(v) for v in g.bounds]
    return json.loads(json.dumps(geom4326)), bbox, frac


def _count_vertices(geom):
    gj = mapping(geom)
    def walk(c):
        if not c:
            return 0
        if isinstance(c[0], (float, int)):
            return 1
        return sum(walk(x) for x in c)
    return walk(gj.get("coordinates", []))


def proj_props(ds):
    """proj:* fields describing the raster itself (unchanged by this script)."""
    epsg = ds.crs.to_epsg() if ds.crs else None
    t = ds.transform
    left, bottom, right, top = ds.bounds
    return {
        **({"proj:epsg": epsg} if epsg else {}),
        "proj:shape": [ds.height, ds.width],
        "proj:transform": [t.a, t.b, t.c, t.d, t.e, t.f, 0.0, 0.0, 1.0],
        "proj:bbox": [left, bottom, right, top],
    }


def asset_dict(path, size_bytes):
    return {
        "href": str(path),
        "type": COG_MEDIA_TYPE,
        "roles": ["visual", "data", "overview"],
        "title": "True-colour RGB (8-bit COG, EPSG:3857, internal mask)",
        "gsd": GSD_M,
        "file:size": size_bytes,
        "eo:bands": RGB_BANDS,
        "raster:bands": [
            {"data_type": "uint8", "bits_per_sample": 8, "name": b["common_name"]}
            for b in RGB_BANDS
        ],
    }


def build_item(path, coll_id, cloud_lut):
    parsed = parse_cog_name(path.name)
    if parsed is None:
        log(f"  WARN unparseable filename, skipped: {path.name}")
        return None
    item_id, tile, orbit, dt, day = parsed

    try:
        size = path.stat().st_size
    except OSError as e:
        log(f"  WARN stat failed {path.name}: {e!r}")
        return None
    if size < MIN_ASSET_BYTES:
        log(f"  WARN suspiciously small ({size} B), skipped: {path.name}")
        return None

    try:
        with rasterio.open(path) as ds:
            # Geometry is derived from the validity mask, so the file must HAVE
            # one. v2 files express validity as nodata=0 (flag: nodata); the
            # earlier alpha-band build expressed it as per_dataset/alpha. Accept
            # any of those and reject only all_valid, which means no mask at all
            # and would silently produce rectangle footprints again.
            flags = ds.mask_flag_enums[0]
            if MaskFlags.all_valid in flags:
                log(f"  WARN no validity mask (all_valid), skipped: {path.name}")
                return None
            fp = valid_footprint(ds)
            if fp is None:
                log(f"  WARN no valid pixels, skipped: {path.name}")
                return None
            geometry, bbox, frac = fp
            pprops = proj_props(ds)
    except Exception as e:
        log(f"  WARN read failed {path.name}: {e!r}")
        return None

    if bbox[2] - bbox[0] > 180:
        log(f"  WARN {path.name}: bbox spans >180 deg, antimeridian? {bbox}")

    props = {
        "datetime": dt,
        "constellation": "sentinel-2",
        "s2:mgrs_tile": tile,
        "sat:absolute_orbit": orbit,
        "gsd": GSD_M,
        "s2:processing_level": "L2A",
        # share of the raster rectangle that actually holds data: 1.0 = full
        # granule, ~0.65 = partial swath. This is what the tightened geometry
        # encodes, surfaced as a property so it is searchable.
        "s2:valid_fraction": round(frac, 5),
        **pprops,
    }

    meta = cloud_lut.get((tile, day))
    if meta:
        if meta["cloud"] is not None:
            props["eo:cloud_cover"] = meta["cloud"]
        if meta["area"] is not None:
            props["s2:area_covered"] = meta["area"]
        if meta["black_area"] is not None:
            props["s2:black_area"] = meta["black_area"]
        if meta["baseline"]:
            props["s2:processing_baseline"] = meta["baseline"]
        if meta["title"]:
            props["s2:product_uri"] = meta["title"]
            plat = meta["title"][:3].upper()
            if plat in ("S2A", "S2B", "S2C"):
                props["platform"] = f"sentinel-2{plat[2].lower()}"
        if meta["datatake"]:
            props["s2:datatake_start"] = meta["datatake"]

    return {
        "type": "Feature",
        "stac_version": "1.1.0",
        "stac_extensions": ITEM_EXTS,
        "id": item_id,
        "geometry": geometry,
        "bbox": bbox,
        "properties": props,
        "links": [],
        "assets": {ASSET_KEY: asset_dict(path, size)},
        "collection": coll_id,
    }


def collection_dict(coll_id, year, xs, ys, dt_min, dt_max, clouds, platforms, fracs):
    summaries = {
        "gsd": [GSD_M],
        "constellation": ["sentinel-2"],
        "proj:epsg": [3857],
    }
    if platforms:
        summaries["platform"] = sorted(platforms)
    if clouds:
        summaries["eo:cloud_cover"] = {"minimum": round(min(clouds), 4),
                                       "maximum": round(max(clouds), 4)}
    if fracs:
        summaries["s2:valid_fraction"] = {"minimum": round(min(fracs), 5),
                                          "maximum": round(max(fracs), 5)}
    return {
        "type": "Collection",
        "id": coll_id,
        "stac_version": "1.1.0",
        "stac_extensions": [EO_EXT, RASTER_EXT, ITEM_ASSETS_EXT, RENDER_EXT],
        "title": f"Sentinel-2 L2A true-colour RGB COGs (valid-data footprints), {year}",
        "description": (
            f"Sentinel-2 L2A true-colour composites for {year}: 8-bit 3-band "
            "cloud-optimized GeoTIFFs in EPSG:3857 with internal overviews and an "
            "internal mask band. Identical raster files to "
            f"sentinel-2-l2a-rgb-cog-masked-{year}; the only difference is that "
            "each item's geometry is the REAL valid-data footprint derived from "
            "the mask, rather than the raster's bounding rectangle. That matters "
            "because pgstac's mosaic shortcuts (skipcovered / exitwhenfull) "
            "compare geometries: with bounding rectangles, all scenes of a tile "
            "look identical and pgstac stops after the first, so a partial "
            "granule leaves holes. Render with assets=visual, no rescale and NO "
            "nodata parameter. Pixel values are contrast-stretched for display "
            "and are NOT reflectance."
        ),
        "license": "other",
        "extent": {
            "spatial": {"bbox": [[min(xs), min(ys), max(xs), max(ys)]] if xs
                        else [[-180, -90, 180, 90]]},
            "temporal": {"interval": [[dt_min, dt_max]]},
        },
        "summaries": summaries,
        "item_assets": {
            ASSET_KEY: {
                "type": COG_MEDIA_TYPE,
                "roles": ["visual", "data", "overview"],
                "title": "True-colour RGB (8-bit COG, EPSG:3857, internal mask)",
                "gsd": GSD_M,
                "eo:bands": RGB_BANDS,
            }
        },
        "renders": {
            "visual": {"title": "True colour", "assets": [ASSET_KEY]}
        },
        "links": [],
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--year", type=int, default=2024)
    ap.add_argument("--smoke", type=int, metavar="N", default=0)
    ap.add_argument("--threads", type=int, default=THREADS)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    year = args.year
    coll_id = COLLECTION_TMPL.format(year=year)
    cog_root = Path(COG_ROOT_TMPL.format(year=year))
    csv_path = CSV_DIR / CSV_TMPL.format(year=year)
    out_dir = OUT_ROOT / (f"rgb_cog_v2_{year}_smoke" if args.smoke
                          else f"rgb_cog_v2_{year}")
    done = out_dir / ".done"

    log(f"collection : {coll_id}")
    log(f"cog root   : {cog_root}")
    log(f"cloud csv  : {csv_path}")
    log(f"out dir    : {out_dir}")
    log(f"footprint  : from internal mask, probe ~{PROBE_PX}px, simplify {SIMPLIFY_PX}px")

    if not cog_root.is_dir():
        sys.exit(f"COG root not found: {cog_root}")
    if done.exists() and not args.force:
        log(f"already built ({done}) — nothing to do. Use --force to rebuild.")
        return
    if not csv_path.exists():
        log(f"WARNING cloud CSV missing, items will have no eo:cloud_cover: {csv_path}")

    cogs = find_cogs(cog_root)
    if args.smoke:
        cogs = cogs[: args.smoke]
    if not cogs:
        sys.exit(f"No *_rgb_3857_cog.tif found under {cog_root}")
    log(f"{len(cogs)} COGs found")

    wanted = set()
    for p in cogs:
        parsed = parse_cog_name(p.name)
        if parsed:
            wanted.add((parsed[1], parsed[4]))
    cloud_lut = load_cloud_lookup(csv_path, wanted) if csv_path.exists() else {}

    out_dir.mkdir(parents=True, exist_ok=True)
    items_path = out_dir / "items.ndjson"
    tmp_path = out_dir / "items.ndjson.partial"

    xs, ys, clouds, fracs, platforms = [], [], [], [], set()
    dt_min = dt_max = None
    n_ok = n_bad = n_nocloud = 0
    n_partial = 0

    with open(tmp_path, "w") as out:
        with ThreadPoolExecutor(max_workers=args.threads) as pool:
            futs = {pool.submit(build_item, p, coll_id, cloud_lut): p for p in cogs}
            for i, fut in enumerate(as_completed(futs), 1):
                try:
                    item = fut.result()
                except Exception as e:
                    log(f"  WARN {futs[fut].name} failed: {e!r}")
                    n_bad += 1
                    continue
                if item is None:
                    n_bad += 1
                    continue
                out.write(json.dumps(item, separators=(",", ":")) + "\n")
                n_ok += 1
                b = item["bbox"]
                xs += [b[0], b[2]]
                ys += [b[1], b[3]]
                d = item["properties"]["datetime"]
                dt_min = d if dt_min is None or d < dt_min else dt_min
                dt_max = d if dt_max is None or d > dt_max else dt_max
                fr = item["properties"]["s2:valid_fraction"]
                fracs.append(fr)
                if fr < PARTIAL_BELOW:
                    n_partial += 1
                if item["properties"].get("platform"):
                    platforms.add(item["properties"]["platform"])
                cc = item["properties"].get("eo:cloud_cover")
                if cc is None:
                    n_nocloud += 1
                else:
                    clouds.append(cc)
                if i % 200 == 0:
                    log(f"  {i}/{len(cogs)} processed, {n_ok} items")

    if n_ok == 0:
        tmp_path.unlink(missing_ok=True)
        sys.exit("No items built — refusing to write an empty catalogue.")
    os.replace(tmp_path, items_path)

    (out_dir / "collection.json").write_text(json.dumps(
        collection_dict(coll_id, year, xs, ys, dt_min, dt_max, clouds, platforms, fracs),
        indent=1))
    done.write_text(json.dumps(
        {"items": n_ok, "skipped": n_bad, "without_cloud": n_nocloud,
         "partial_granules": n_partial, "collection": coll_id, "year": year},
        indent=1) + "\n")

    log("")
    log(f"DONE  {n_ok} items -> {items_path}")
    log(f"      {n_bad} skipped, {n_nocloud} without eo:cloud_cover")
    log(f"      {n_partial} genuinely partial granules (valid_fraction < {PARTIAL_BELOW};"
        f" a full granule reads ~0.95 because of the reprojection pad)")
    log(f"      valid_fraction min={min(fracs):.4f} median={sorted(fracs)[len(fracs)//2]:.4f}")
    log(f"      bbox   {min(xs):.4f},{min(ys):.4f},{max(xs):.4f},{max(ys):.4f}")
    log(f"      time   {dt_min} .. {dt_max}")
    log("")
    log("Next:  ./load_cog_stac_poly.sh   (loads into pgstac as a NEW collection)")


if __name__ == "__main__":
    main()
