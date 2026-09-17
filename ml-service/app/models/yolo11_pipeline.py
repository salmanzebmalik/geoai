from pathlib import Path
import time

import geopandas as gpd
import numpy as np
import pandas as pd
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

    Supports native single-pass inference for small chips and automated
    sliding-window tiling for large-scale raster inputs.
    Native resolution of the yolo11 trained model is 800x800
    """

    def __init__(
        self,
        model_path: str = "app/models/yolo11/best_yolo11v1.pt",
        conf_min: float = 0.25,
        imgsz: int = 800,
        tile_size: int = 800,
        overlap: int = 100,
    ):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.conf_min = conf_min
        self.imgsz = imgsz
        self.tile_size = tile_size
        self.overlap = overlap

        path = Path(model_path)
        if not path.exists():
            raise FileNotFoundError(f"YOLO11 checkpoint not found at {path}.")

        logger.info(f"Loading YOLO11 weights from {path} onto {self.device}...")
        self.model = YOLO(str(path))
        try:
            self.model.to(self.device)
        except Exception as e:
            logger.warning(f"Could not move model explicitly to {self.device}: {e}")

    def _preprocess_image(self, img_array: np.ndarray) -> np.ndarray:
        """Applies 2nd-98th percentile contrast stretching for raw satellite imagery."""
        img = img_array.astype(np.float32)
        for i in range(img.shape[-1]):
            band = img[:, :, i]
            p2, p98 = np.percentile(band, (2, 98))
            img[:, :, i] = np.clip((band - p2) / (p98 - p2 + 1e-8) * 255.0, 0, 255)
        return img.astype(np.uint8)

    @torch.inference_mode()
    def predict_boxes_geojson(self, image_bytes: bytes) -> dict:
        start = time.time()

        with rasterio.MemoryFile(image_bytes) as memfile, memfile.open() as src:
            width, height = src.width, src.height
            crs = src.crs
            bounds = src.bounds

            if crs is None:
                raise ValueError("Input image has no CRS; cannot georeference predictions.")

            # Automated branching: Single pass for small images, Tiling for large scale
            if width <= self.tile_size and height <= self.tile_size:
                channels = [1, 2, 3] if src.count >= 3 else [1, 1, 1]
                raw_img = np.moveaxis(src.read(channels), 0, -1)
                if raw_img.dtype == np.uint16:
                    raw_img = (raw_img / 256).astype(np.uint8)
                img = self._preprocess_image(raw_img)

                results = self.model.predict(
                    source=np.ascontiguousarray(img),
                    conf=self.conf_min,
                    imgsz=self.imgsz,
                    device=self.device,
                    verbose=False,
                )

                if not results or len(results[0].boxes) == 0:
                    return {"type": "FeatureCollection", "features": []}

                transform = from_bounds(*bounds, width, height)
                geoms, scores, class_ids, class_names = [], [], [], []

                for box in results[0].boxes:
                    xyxy = box.xyxy[0].cpu().numpy()
                    score = float(box.conf[0].cpu().item())
                    cls_id = int(box.cls[0].cpu().item())
                    xmin, ymin, xmax, ymax = xyxy
                    x0, y0 = xy(transform, ymin, xmin, offset="ul")
                    x1, y1 = xy(transform, ymax, xmax, offset="ul")
                    geoms.append(shp_box(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)))
                    scores.append(score)
                    class_ids.append(cls_id)
                    class_names.append(self.model.names[cls_id])

                gdf = gpd.GeoDataFrame(
                    {"score": scores, "class_id": class_ids, "class": class_names},
                    geometry=geoms,
                    crs=crs,
                )
            else:
                step = self.tile_size - self.overlap
                all_gdfs = []

                for y in range(0, height, step):
                    for x in range(0, width, step):
                        w_width = min(self.tile_size, width - x)
                        w_height = min(self.tile_size, height - y)
                        window = rasterio.windows.Window(x, y, w_width, w_height)

                        channels = [1, 2, 3] if src.count >= 3 else [1, 1, 1]
                        window_data = src.read(channels, window=window)
                        raw_img = np.moveaxis(window_data, 0, -1)
                        if raw_img.dtype == np.uint16:
                            raw_img = (raw_img / 256).astype(np.uint8)
                        img = self._preprocess_image(raw_img)

                        results = self.model.predict(
                            source=np.ascontiguousarray(img),
                            conf=self.conf_min,
                            imgsz=self.imgsz,
                            device=self.device,
                            verbose=False,
                        )

                        if not results or len(results[0].boxes) == 0:
                            continue

                        window_transform = rasterio.windows.transform(window, src.transform)
                        geoms, scores, class_ids, class_names = [], [], [], []

                        for box in results[0].boxes:
                            xyxy = box.xyxy[0].cpu().numpy()
                            score = float(box.conf[0].cpu().item())
                            cls_id = int(box.cls[0].cpu().item())
                            xmin, ymin, xmax, ymax = xyxy
                            x0, y0 = xy(window_transform, ymin, xmin, offset="ul")
                            x1, y1 = xy(window_transform, ymax, xmax, offset="ul")
                            geoms.append(shp_box(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)))
                            scores.append(score)
                            class_ids.append(cls_id)
                            class_names.append(self.model.names[cls_id])

                        tile_gdf = gpd.GeoDataFrame(
                            {"score": scores, "class_id": class_ids, "class": class_names},
                            geometry=geoms,
                            crs=crs,
                        )
                        all_gdfs.append(tile_gdf)

                if not all_gdfs:
                    return {"type": "FeatureCollection", "features": []}

                gdf = pd.concat(all_gdfs, ignore_index=True)
                gdf = gpd.GeoDataFrame(gdf, geometry="geometry", crs=crs)
                gdf = gdf.drop_duplicates(subset=["geometry"])

        if not gdf.empty:
            gdf["area_m2"] = _area_m2(gdf)
            gdf = gdf.to_crs("EPSG:4326")

        logger.info(
            f"YOLO11 inference complete | {len(gdf)} detections | {time.time() - start:.2f}s"
        )
        return gdf.__geo_interface__