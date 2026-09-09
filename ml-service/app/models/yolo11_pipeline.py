from pathlib import Path
import time

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import xy
from shapely.geometry import box as shp_box
import torch
from ultralytics import YOLO

from app.utils.instancing import _area_m2
from app.utils.logger import get_logger

logger = get_logger(__name__)


class YOLO26Pipeline:
    """Production-grade YOLO26 Object Detection Pipeline for geospatial raster imagery.

    Supports single-pass inference for small chips and automated
    sliding-window tiling for large-scale rasters, custom-tailored for
    yolo26l.pt operating at a native resolution of 1024x1024 with a 20% overlap.
    """

    def __init__(
            self,
            model_path: str = "app/models/download_models/yolo26/best_yolo26l_v1.pt",
            conf_min: float = 0.35,
            imgsz: int = 1024,
            tile_size: int = 1024,
            overlap: int = 205,  # 20% overlap matching training slicing pipeline (~819px stride)
    ):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.conf_min = conf_min
        self.imgsz = imgsz
        self.tile_size = tile_size
        self.overlap = overlap

        path = Path(model_path)
        if not path.exists():
            raise FileNotFoundError(f"YOLO26 checkpoint not found at {path}.")

        logger.info(f"Loading YOLO26 weights from {path} onto {self.device}...")
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

        # Load raster imagery safely from memory buffer
        with rasterio.MemoryFile(image_bytes) as memfile, memfile.open() as src:
            width, height = src.width, src.height
            crs = src.crs
            bounds = src.bounds

            if crs is None:
                raise ValueError("Input image has no CRS; cannot georeference predictions.")

            # --- BRANCH 1: Single-pass inference for small rasters ---
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

                transform = rasterio.transform.from_bounds(*bounds, width, height)
                geoms, scores, class_ids, class_names = [], [], [], []

                for box in results[0].boxes:
                    xyxy = box.xyxy[0].cpu().numpy()
                    score = float(box.conf[0].cpu().item())
                    cls_id = int(box.cls[0].cpu().item())
                    xmin, ymin, xmax, ymax = xyxy

                    # Transform pixel coordinates to geospatial CRS coordinates
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

            # --- BRANCH 2: Sliding-window tiling for large-scale rasters ---
            else:
                step = self.tile_size - self.overlap
                all_gdfs = []

                # Iterate through raster using sliding windows
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

                        # Pad edge tiles with zeros to match exact 1024x1024 tensor input requirements
                        if raw_img.shape[0] < self.tile_size or raw_img.shape[1] < self.tile_size:
                            padded_img = np.zeros((self.tile_size, self.tile_size, raw_img.shape[2]),
                                                  dtype=raw_img.dtype)
                            padded_img[0:raw_img.shape[0], 0:raw_img.shape[1]] = raw_img
                            raw_img = padded_img

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

                            # Clamp coordinates to actual window bounds (ignoring padding regions)
                            xmin = min(xmin, w_width)
                            xmax = min(xmax, w_width)
                            ymin = min(ymin, w_height)
                            ymax = min(ymax, w_height)

                            if xmax <= xmin or ymax <= ymin:
                                continue

                            # Map local window predictions to master geospatial coordinates
                            x0, y0 = xy(window_transform, ymin, xmin, offset="ul")
                            x1, y1 = xy(window_transform, ymax, xmax, offset="ul")
                            geoms.append(shp_box(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)))
                            scores.append(score)
                            class_ids.append(cls_id)
                            class_names.append(self.model.names[cls_id])

                        if geoms:
                            tile_gdf = gpd.GeoDataFrame(
                                {"score": scores, "class_id": class_ids, "class": class_names},
                                geometry=geoms,
                                crs=crs,
                            )
                            all_gdfs.append(tile_gdf)

                if not all_gdfs:
                    return {"type": "FeatureCollection", "features": []}

                # Concatenate all tile dataframes and remove boundary duplicates from overlapping zones
                gdf = pd.concat(all_gdfs, ignore_index=True)
                gdf = gpd.GeoDataFrame(gdf, geometry="geometry", crs=crs)
                gdf = gdf.drop_duplicates(subset=["geometry", "class_id"])

        # Calculate bounding box physical areas and reproject to WGS84 for GeoJSON export
        if not gdf.empty:
            gdf["area_m2"] = _area_m2(gdf)
            gdf = gdf.to_crs("EPSG:4326")

        logger.info(
            f"YOLO26 inference complete | {len(gdf)} detections | {time.time() - start:.2f}s"
        )
        return gdf.__geo_interface__