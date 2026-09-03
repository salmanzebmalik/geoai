from pathlib import Path
import time

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.transform import from_bounds, xy
from shapely.geometry import box as shp_box
import torch
from ultralytics import YOLO

from app.utils.instancing import _area_m2
from app.utils.logger import get_logger

logger = get_logger(__name__)


class YOLO11Pipeline:
    """YOLO11 Object Detection Pipeline for geospatial raster imagery.

    Detects objects, maps pixel bounding boxes to geospatial coordinates,
    and returns a standard GeoJSON FeatureCollection.
    """

    def __init__(
        self,
        model_path: str = "app/models/download_models/yolo11/best_yolo11v1.pt",
        conf_min: float = 0.25,
        imgsz: int = 800,
    ):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.conf_min = conf_min
        self.imgsz = imgsz

        path = Path(model_path)
        if not path.exists():
            raise FileNotFoundError(f"YOLO11 checkpoint not found at {path}.")

        logger.info(f"Loading YOLO11 weights from {path} onto {self.device}...")
        self.model = YOLO(str(path))
        try:
            self.model.to(self.device)
        except Exception as e:
            logger.warning(f"Could not move model explicitly to {self.device}: {e}")

    @torch.inference_mode()
    def predict_boxes_geojson(self, image_bytes: bytes) -> dict:
        start = time.time()

        # 1. Load raster image bytes and extract spatial metadata
        with rasterio.MemoryFile(image_bytes) as memfile, memfile.open() as src:
            img = np.moveaxis(src.read([1, 2, 3]), 0, -1)
            if img.dtype == np.uint16:
                img = (img / 256).astype(np.uint8)
            h, w = img.shape[:2]

            if src.crs is None:
                raise ValueError("Input image has no CRS; cannot georeference the prediction.")

            bounds, crs = src.bounds, src.crs

        # 2. Run YOLO11 inference
        results = self.model.predict(
            source=np.ascontiguousarray(img),
            conf=self.conf_min,
            imgsz=self.imgsz,
            device=self.device,
            verbose=False,
        )

        if not results or len(results[0].boxes) == 0:
            logger.info("YOLO11 inference complete | 0 detections")
            return {"type": "FeatureCollection", "features": []}

        boxes = results[0].boxes

        # 3. Transform pixel coordinates -> Raster's spatial CRS
        transform = from_bounds(*bounds, w, h)
        geoms = []
        scores = []
        class_ids = []
        class_names = []

        for box in boxes:
            xyxy = box.xyxy[0].cpu().numpy()
            score = float(box.conf[0].cpu().item())
            cls_id = int(box.cls[0].cpu().item())
            cls_name = self.model.names[cls_id]

            xmin, ymin, xmax, ymax = xyxy

            # Convert bounding box corners from pixels to ground coordinates
            x0, y0 = xy(transform, ymin, xmin, offset="ul")
            x1, y1 = xy(transform, ymax, xmax, offset="ul")

            geoms.append(shp_box(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)))
            scores.append(score)
            class_ids.append(cls_id)
            class_names.append(cls_name)

        # 4. Create GeoDataFrame and post-process
        gdf = gpd.GeoDataFrame(
            {
                "score": scores,
                "class_id": class_ids,
                "class": class_names,
            },
            geometry=geoms,
            crs=crs,
        )

        gdf["area_m2"] = _area_m2(gdf)
        gdf = gdf.to_crs("EPSG:4326")

        logger.info(
            f"YOLO11 inference complete | {len(gdf)} detections | {time.time() - start:.2f}s"
        )
        return gdf.__geo_interface__