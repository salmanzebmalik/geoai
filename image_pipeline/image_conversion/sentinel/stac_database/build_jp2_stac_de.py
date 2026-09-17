#!/usr/bin/env python3
"""
Build a STAC collection for the RAW 16-bit Sentinel-2 L2A .jp2 granules,
restricted to the 106 German MGRS tiles, with REAL valid-data footprints.
"""

import argparse
import csv
import json
import os
import re
import sys
import time
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

warnings.filterwarnings("ignore", category=DeprecationWarning)

import numpy as np
import rasterio
from rasterio import features
from rasterio.enums import MaskFlags
from rasterio.warp import transform_bounds, transform_geom
from shapely.geometry import mapping, shape
from shapely.ops import unary_union

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
RAW_TMPL = "/home/ubuntu/work/satellite_data/raw_sentinel_data/worldwide_{year}_only_download"
COG_TMPL = "/home/ubuntu/work/saved_data/collections/sentinel_rgb_cogs_v2/{year}"
TILE_LIST = Path("/home/ubuntu/work/saved_data/collections/germany_tiles.txt")
CSV_DIR = Path("/home/ubuntu/work/saved_data/collections/sentinel")
CSV_TMPL = "links_worldwide_{year}.final.csv"

OUT_ROOT = Path(__file__).resolve().parent / "out"
COLLECTION_TMPL = "sentinel-2-l2a-jp2-de-{year}"

THREADS = 16
MIN_ASSET_BYTES = 100_000

# The 12 L2A bands, matching the asset keys the worldwide collections use.
# B10 (cirrus) is deliberately absent: it exists only in L1C, is consumed by the
# atmospheric correction, and is not carried into L2A products.
BANDS = [
    ("B01", 60, "coastal", 0.443),
    ("B02", 10, "blue",    0.490),
    ("B03", 10, "green",   0.560),
    ("B04", 10, "red",     0.665),
    ("B05", 20, "rededge", 0.705),
    ("B06", 20, "rededge", 0.740),
    ("B07", 20, "rededge", 0.783),
    ("B08", 10, "nir",     0.842),
    ("B8A", 20, "nir08",   0.865),
    ("B09", 60, "nir09",   0.945),
    ("B11", 20, "swir16",  1.610),
    ("B12", 20, "swir22",  2.190),
]
JP2_MEDIA_TYPE = "image/jp2"

# Footprint derivation (same parameters as build_cog_stac_v2.py, so the two
# collections describe identical geometry for identical granules).
PROBE_PX = 1024
MIN_BLOB_PX = 24
SIMPLIFY_PX = 1.5
MAX_VERTICES = 1500
PARTIAL_BELOW = 0.85

EO_EXT     = "https://stac-extensions.github.io/eo/v1.1.0/schema.json"
PROJ_EXT   = "https://stac-extensions.github.io/projection/v1.1.0/schema.json"
SAT_EXT    = "https://stac-extensions.github.io/sat/v1.0.0/schema.json"
FILE_EXT   = "https://stac-extensions.github.io/file/v2.1.0/schema.json"
ITEM_ASSETS_EXT = "https://stac-extensions.github.io/item-assets/v1.0.0/schema.json"
ITEM_EXTS = [EO_EXT, PROJ_EXT, SAT_EXT, FILE_EXT]

GRANULE_RE = re.compile(r"^L2A_(T\w{5})_A(\d+)_(\d{8}T\d{6})$")

T0 = time.time()


def log(msg):
    print(f"[{time.time() - T0:8.1f}s] {msg}", flush=True)


def parse_granule(name):
    m = GRANULE_RE.match(name)
    if not m:
        return None
    tile, orbit, stamp = m.group(1), m.group(2), m.group(3)
    d, t = stamp[:8], stamp[9:]
    dt = f"{d[:4]}-{d[4:6]}-{d[6:8]}T{t[:2]}:{t[2:4]}:{t[4:6]}Z"
    day = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
    return tile, int(orbit), dt, day


def load_cloud_lookup(csv_path, wanted):
    """(tile, day) -> cloud etc. cloudCover in the CSV is a 0-1 FRACTION and
    eo:cloud_cover is percent, hence the x100. Join on the DATE, not the
    timestamp: the CSV holds the datatake start while the granule name holds
    the sensing time, so they differ by minutes."""
    lut = {}
    n = 0
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            n += 1
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
                "baseline": (row.get("processingBaseline") or "").strip() or None,
                "title": (row.get("title") or "").strip() or None,
                "datatake": (row.get("startDate") or "").strip() or None,
            }
    log(f"  CSV: {n} rows scanned, {len(lut)}/{len(wanted)} needed keys resolved")
    return lut


def _count_vertices(geom):
    def walk(c):
        if not c:
            return 0
        if isinstance(c[0], (float, int)):
            return 1
        return sum(walk(x) for x in c)
    return walk(mapping(geom).get("coordinates", []))


def valid_footprint(cog_path):
    """(geometry_4326, bbox_4326, valid_fraction) from the COG's internal mask."""
    with rasterio.open(cog_path) as ds:
        if MaskFlags.all_valid in ds.mask_flag_enums[0]:
            return None
        f = max(1, int(round(max(ds.width, ds.height) / PROBE_PX)))
        h, w = max(1, ds.height // f), max(1, ds.width // f)
        mask = ds.read_masks(1, out_shape=(h, w)).astype(bool)
        frac = float(mask.mean())
        if not mask.any():
            return None
        probe_tf = ds.transform * rasterio.Affine.scale(ds.width / w, ds.height / h)
        px = max(abs(probe_tf.a), abs(probe_tf.e))
        crs = ds.crs

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
    for _ in range(6):
        if _count_vertices(simple) <= MAX_VERTICES:
            break
        tol *= 2
        simple = merged.simplify(tol, preserve_topology=True)
    if simple.is_empty:
        simple = merged
    # buffer(0) repairs self-touching rings that simplify can leave behind on
    # disjoint valid regions; without it a few items land in the DB as invalid
    # geometry, which makes PostGIS operations unpredictable.
    if not simple.is_valid:
        simple = simple.buffer(0)
    if simple.is_empty or not simple.is_valid:
        return None

    geom4326 = transform_geom(crs, "EPSG:4326", mapping(simple), precision=7)
    g = shape(geom4326)
    # Re-validate AFTER reprojection, not just before. Validating in the source
    # CRS is not enough: transform_geom rounds to `precision` decimal places,
    # which can pull two nearly-coincident vertices onto each other and create a
    # self-intersection that did not exist in the projected geometry. Six items
    # reached the DB that way on the first 2022 run, where PostGIS reported
    # self-intersections that shapely had already passed as valid.
    if not g.is_valid:
        g = g.buffer(0)
    if g.is_empty or not g.is_valid:
        return None
    return json.loads(json.dumps(mapping(g))), [float(v) for v in g.bounds], frac


def build_item(granule_dir, cog_path, coll_id, cloud_lut):
    gname = granule_dir.name
    parsed = parse_granule(gname)
    if parsed is None:
        log(f"  WARN unparseable granule name, skipped: {gname}")
        return None
    tile, orbit, dt, day = parsed

    # every band must be present and non-truncated; the raw archive contains
    # 0-byte failed downloads and granules missing bands entirely
    assets = {}
    for band, gsd, common, wl in BANDS:
        p = granule_dir / f"{gname}_{band}_{gsd}m.jp2"
        try:
            size = p.stat().st_size
        except OSError:
            log(f"  MISS {gname}: no {band}")
            return None
        if size < MIN_ASSET_BYTES:
            log(f"  MISS {gname}: {band} truncated ({size} B)")
            return None
        assets[band] = {
            "href": str(p),
            "type": JP2_MEDIA_TYPE,
            "roles": ["data"],
            "title": f"{common} ({gsd}m)",
            "gsd": gsd,
            "file:size": size,
            "eo:bands": [{"name": band, "common_name": common,
                          "center_wavelength": wl}],
        }

    fp = valid_footprint(cog_path)
    if fp is None:
        log(f"  WARN no usable footprint from COG, skipped: {gname}")
        return None
    geometry, bbox, frac = fp

    # proj:* describes the SOURCE raster, so read it from a .jp2 header, not
    # from the reprojected COG. B01 is 60 m (1830x1830) so it is the cheapest
    # header to open.
    try:
        with rasterio.open(assets["B01"]["href"]) as ds:
            epsg = ds.crs.to_epsg() if ds.crs else None
    except Exception as e:
        log(f"  WARN could not read source CRS {gname}: {e!r}")
        epsg = None

    props = {
        "datetime": dt,
        "constellation": "sentinel-2",
        "s2:mgrs_tile": tile,
        "sat:absolute_orbit": orbit,
        "s2:processing_level": "L2A",
        "s2:valid_fraction": round(frac, 5),
        **({"proj:epsg": epsg} if epsg else {}),
    }

    meta = cloud_lut.get((tile, day))
    if meta:
        if meta["cloud"] is not None:
            props["eo:cloud_cover"] = meta["cloud"]
        if meta["area"] is not None:
            props["s2:area_covered"] = meta["area"]
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
        "id": gname,
        "geometry": geometry,
        "bbox": bbox,
        "properties": props,
        "links": [],
        "assets": assets,
        "collection": coll_id,
    }


def collection_dict(coll_id, year, xs, ys, dt_min, dt_max, clouds, platforms, fracs):
    summaries = {"constellation": ["sentinel-2"],
                 "gsd": sorted({g for _, g, _, _ in BANDS})}
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
        "stac_extensions": [EO_EXT, ITEM_ASSETS_EXT],
        "title": f"Sentinel-2 L2A raw .jp2 bands, Germany, {year}",
        "description": (
            f"Raw 16-bit Sentinel-2 L2A granules for {year}, restricted to the "
            "106 German MGRS tiles. Twelve assets per item, one per band, "
            "pointing at the original .jp2 files -- identical data to the "
            f"sentinel-2-l2a-worldwide-{year} collection. The difference is the "
            "item geometry: here it is the REAL valid-data footprint derived "
            "from the granule's non-nodata region, whereas the worldwide "
            "collection uses the full MGRS tile outline. That matters because "
            "pgstac's mosaic shortcuts (skipcovered / exitwhenfull) compare "
            "geometries: with tile outlines, a partial granule claims coverage "
            "it lacks, pgstac stops early, and a bbox crop over that area comes "
            "back blank. Values are reflectance, so render with "
            "assets=B04&assets=B03&assets=B02&rescale=0,3000 for true colour."
        ),
        "license": "other",
        "extent": {
            "spatial": {"bbox": [[min(xs), min(ys), max(xs), max(ys)]] if xs
                        else [[-180, -90, 180, 90]]},
            "temporal": {"interval": [[dt_min, dt_max]]},
        },
        "summaries": summaries,
        "item_assets": {
            band: {"type": JP2_MEDIA_TYPE, "roles": ["data"], "gsd": gsd,
                   "title": f"{common} ({gsd}m)",
                   "eo:bands": [{"name": band, "common_name": common,
                                 "center_wavelength": wl}]}
            for band, gsd, common, wl in BANDS
        },
        "links": [],
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--smoke", type=int, metavar="N", default=0)
    ap.add_argument("--threads", type=int, default=THREADS)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    year = args.year
    coll_id = COLLECTION_TMPL.format(year=year)
    raw_root = Path(RAW_TMPL.format(year=year))
    cog_root = Path(COG_TMPL.format(year=year))
    csv_path = CSV_DIR / CSV_TMPL.format(year=year)
    out_dir = OUT_ROOT / (f"jp2_de_{year}_smoke" if args.smoke else f"jp2_de_{year}")
    done = out_dir / ".done"

    log(f"collection : {coll_id}")
    log(f"raw root   : {raw_root}")
    log(f"cog root   : {cog_root}   (footprints come from here)")
    log(f"tile list  : {TILE_LIST}")
    log(f"out dir    : {out_dir}")

    if not raw_root.is_dir():
        sys.exit(f"raw root not found: {raw_root}")
    if not cog_root.is_dir():
        sys.exit(f"COG root not found: {cog_root}\n"
                 f"Convert {year} to COGs first (convertjp2tocog_v2.sh) -- this "
                 f"script derives footprints from the COG masks.")
    if not TILE_LIST.is_file():
        sys.exit(f"tile list not found: {TILE_LIST}")
    if done.exists() and not args.force:
        log(f"already built ({done}) — nothing to do. Use --force to rebuild.")
        return

    tiles = [t.strip() for t in TILE_LIST.read_text().split("\n") if t.strip()]
    log(f"{len(tiles)} tiles in the list")

    # pair each granule with its COG; a granule with no COG cannot be catalogued
    work, no_cog = [], 0
    for tile in tiles:
        tdir = raw_root / tile
        if not tdir.is_dir():
            continue
        for gdir in sorted(tdir.glob("L2A_*")):
            if not gdir.is_dir():
                continue
            cog = cog_root / tile / f"{gdir.name}_rgb_3857_cog.tif"
            if not cog.is_file():
                no_cog += 1
                continue
            work.append((gdir, cog))
    if args.smoke:
        work = work[: args.smoke]
    if not work:
        sys.exit("no granules with a matching COG found")
    log(f"{len(work)} granules to catalogue"
        + (f", {no_cog} skipped (no COG yet)" if no_cog else ""))

    wanted = set()
    for gdir, _ in work:
        p = parse_granule(gdir.name)
        if p:
            wanted.add((p[0], p[3]))
    cloud_lut = load_cloud_lookup(csv_path, wanted) if csv_path.exists() else {}
    if not csv_path.exists():
        log(f"WARNING cloud CSV missing, no eo:cloud_cover: {csv_path}")

    out_dir.mkdir(parents=True, exist_ok=True)
    items_path = out_dir / "items.ndjson"
    tmp_path = out_dir / "items.ndjson.partial"

    xs, ys, clouds, fracs, platforms = [], [], [], [], set()
    dt_min = dt_max = None
    n_ok = n_bad = n_nocloud = n_partial = 0

    with open(tmp_path, "w") as out:
        with ThreadPoolExecutor(max_workers=args.threads) as pool:
            futs = {pool.submit(build_item, g, c, coll_id, cloud_lut): g
                    for g, c in work}
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
                    log(f"  {i}/{len(work)} processed, {n_ok} items")

    if n_ok == 0:
        tmp_path.unlink(missing_ok=True)
        sys.exit("no items built — refusing to write an empty catalogue")
    os.replace(tmp_path, items_path)

    (out_dir / "collection.json").write_text(json.dumps(
        collection_dict(coll_id, year, xs, ys, dt_min, dt_max, clouds, platforms, fracs),
        indent=1))
    done.write_text(json.dumps(
        {"items": n_ok, "skipped": n_bad, "without_cloud": n_nocloud,
         "partial_granules": n_partial, "no_cog": no_cog,
         "collection": coll_id, "year": year}, indent=1) + "\n")

    log("")
    log(f"DONE  {n_ok} items -> {items_path}")
    log(f"      {n_bad} skipped, {n_nocloud} without eo:cloud_cover")
    log(f"      {n_partial} genuinely partial granules (valid_fraction < {PARTIAL_BELOW})")
    log(f"      bbox {min(xs):.4f},{min(ys):.4f},{max(xs):.4f},{max(ys):.4f}")
    log(f"      time {dt_min} .. {dt_max}")
    log("")
    log(f"Next:  ./load_jp2_stac_de.sh {year}")


if __name__ == "__main__":
    main()
