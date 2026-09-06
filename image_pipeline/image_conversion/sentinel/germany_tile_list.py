#!/usr/bin/env python3

import pandas as pd
from shapely import wkt
from shapely.geometry import box

CSV_PATH = "/home/ubuntu/work/saved_data/collections/sentinel/links_worldwide_2024.final.csv"
OUT_PATH = "/home/ubuntu/work/saved_data/collections/germany_tiles.txt"

# Großzügige Deutschland-BBox
germany_bbox = box(5.0, 46.5, 16.0, 55.5)

df = pd.read_csv(CSV_PATH)

tile_col = "tileId"
wkt_col = "polygon"

df["geometry"] = df[wkt_col].apply(wkt.loads)

df_germany = df[df["geometry"].apply(lambda geom: geom.intersects(germany_bbox))]

tiles = sorted(df_germany[tile_col].dropna().unique())

with open(OUT_PATH, "w") as f:
    for tile in tiles:
        f.write(str(tile) + "\n")

print(f"Found {len(tiles)} Germany-ish tiles")
print(f"Wrote: {OUT_PATH}")