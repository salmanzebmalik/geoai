from pathlib import Path
import time

import numpy as np
import torch
import rasterio
from rasterio.transform import from_bounds, xy
import geopandas as gpd
from shapely.geometry import box as shp_box

from app.utils.instancing import _area_m2
from app.utils.logger import get_logger
logger = get_logger(__name__)


class DeepForestPipeline:
    """-Per-tree crown detection for 10cm RGB ortho imagery. Pretrained DeepForest RetinaNet; 
    - outputs one bounding box per tree
    - This models keeps the bounding boxes, so it does not go through instancing.py"""

    def __init__(self, checkpoint_path: str | None = None, patch_size: int = 400,
                 overlap: float = 0.1, score_min: float = 0.1):
        from deepforest import main  

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.patch_size = patch_size
        self.overlap = overlap
        self.score_min = score_min

        self.model = main.deepforest()
        if checkpoint_path is not None:  # optional fine-tuned weights
            path = Path(checkpoint_path)
            if not path.exists():
                raise FileNotFoundError(f"DeepForest checkpoint not found at {path}.")
            self.model.load_state_dict(torch.load(path, map_location=self.device))
            logger.info(f"DeepForest checkpoint loaded from {path}")
        else:
            try:
                self.model.load_model("weecology/deepforest-tree")  # pretrained crowns (HF)
            except Exception:
                self.model.use_release()                            # older deepforest API
        try:
            self.model.to(self.device)
        except Exception:
            pass

    @torch.inference_mode()
    def predict_boxes_geojson(self, image_bytes: bytes) -> dict:
        start = time.time()
        with rasterio.MemoryFile(image_bytes) as memfile, memfile.open() as src:
            img = np.moveaxis(src.read([1, 2, 3]), 0, -1)
            if img.dtype == np.uint16:
                img = (img / 256).astype(np.uint8)
            h, w = img.shape[:2]
            if src.crs is None:
                raise ValueError("Input image has no CRS; cannot georeference the prediction.")
            bounds, crs = src.bounds, src.crs

        boxes = self.model.predict_tile(
            image=np.ascontiguousarray(img),
            patch_size=self.patch_size,
            patch_overlap=self.overlap,
        )
        if boxes is None or len(boxes) == 0:
            return {"type": "FeatureCollection", "features": []}
        boxes = boxes[boxes.score >= self.score_min]

        # pixel coords -> the raster's own CRS (same georef the service uses)
        transform = from_bounds(*bounds, w, h)
        geoms = []
        for r in boxes.itertuples():
            x0, y0 = xy(transform, r.ymin, r.xmin, offset="ul")
            x1, y1 = xy(transform, r.ymax, r.xmax, offset="ul")
            geoms.append(shp_box(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)))

        gdf = gpd.GeoDataFrame({"score": boxes.score.values}, geometry=geoms, crs=crs)
        gdf["class"] = "tree"
        gdf["area_m2"] = _area_m2(gdf)
        gdf = gdf.to_crs("EPSG:4326")
        logger.info(f"DeepForest inference complete | {len(gdf)} trees | {time.time() - start:.2f}s")
        return gdf.__geo_interface__
