import sys
import numpy as np
import geopandas as gpd
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent / "app" / "models"))
from treepipeline import InferencePipeline


def main():
    #  For testing purposes so file gets .jp2 file gets recognized
    import os
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    # ----- fixed
    image_path = "dop10rgbi_32_280_5652_1_nw_2025.jp2" 
    bbox = (7.615, 51.955, 7.625, 51.965)               # (min_lon, min_lat, max_lon, max_lat)
    
    # --- inference and result as gdf
    pipeline = InferencePipeline()
    mask = pipeline.get_full_mask(image_path)
    result = pipeline.bbox_to_tree_geojson(bbox, mask)

if __name__ == "__main__":
    main()