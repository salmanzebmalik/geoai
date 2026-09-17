from pathlib import Path
import time

import geopandas as gpd
import numpy as np
import rasterio
import torch
from rasterio.enums import Resampling
from rasterio.transform import xy
from shapely.geometry import box as shp_box
from torchvision.ops import batched_nms
from ultralytics import YOLO

from app.utils.instancing import _area_m2
from app.utils.logger import get_logger

logger = get_logger(__name__)

# The model was trained on xView, which is 0.3 m WorldView-3 imagery. Objects have to
# appear at that scale: on a 10 cm orthophoto a car is 3x larger than anything it saw.
XVIEW_GSD_M = 0.3


class YOLO26Pipeline:
    """YOLO26 object detection on a georeferenced crop, tiled with cross-tile NMS."""

    def __init__(
            self,
            model_path: str | None = None,
            conf_min: float = 0.15,
            imgsz: int = 1024,
            tile_size: int = 1024,
            overlap: int = 205,
            iou: float = 0.5,
            target_gsd: float | None = XVIEW_GSD_M,
    ):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.conf_min = conf_min
        self.imgsz = imgsz
        self.tile_size = tile_size
        self.overlap = overlap
        self.iou = iou
        self.target_gsd = target_gsd # 0.1 -> 0.3 xview resolution

        path = Path(model_path) if model_path else (
            Path(__file__).parent / "yolo26" / "best_yolo26l_v1.pt"
        )
        if not path.exists():
            raise FileNotFoundError(f"YOLO26 checkpoint not found at {path}.")

        logger.info(f"Loading YOLO26 weights from {path} onto {self.device}...")
        self.model = YOLO(str(path))
        try:
            self.model.to(self.device)
        except Exception as e:
            logger.warning(f"Could not move model explicitly to {self.device}: {e}")

    def _read_at_training_scale(self, src) -> tuple[np.ndarray, rasterio.Affine]:
        """The crop as (H, W, 3) BGR uint8 at target_gsd, and the transform for that grid."""
        scale = 1.0
        if self.target_gsd and src.crs.is_projected:
            scale = min(1.0, src.res[0] / self.target_gsd)  # only ever downsample
        height = max(1, round(src.height * scale))
        width = max(1, round(src.width * scale))

        bands = [1, 2, 3] if src.count >= 3 else [1, 1, 1]
        data = src.read(bands, out_shape=(len(bands), height, width), resampling=Resampling.average)
        if data.dtype == np.uint16:
            data = (data // 256).astype(np.uint8)

        transform = src.transform * rasterio.Affine.scale(src.width / width, src.height / height)
        # Ultralytics treats numpy input as OpenCV BGR; rasterio returns RGB
        return np.ascontiguousarray(np.moveaxis(data, 0, -1)[..., ::-1]), transform

    def _tile_origins(self, length: int) -> list[int]:
        if length <= self.tile_size:
            return [0]
        step = self.tile_size - self.overlap
        # last tile sits flush with the edge instead of being a thin remainder
        return sorted({min(pos, length - self.tile_size) for pos in range(0, length, step)})

    @torch.inference_mode()
    def predict_boxes_geojson(self, image_bytes: bytes) -> dict:
        start = time.time()

        with rasterio.MemoryFile(image_bytes) as memfile, memfile.open() as src:
            if src.crs is None:
                raise ValueError("Input image has no CRS; cannot georeference predictions.")
            crs = src.crs
            image, transform = self._read_at_training_scale(src)

        height, width = image.shape[:2]
        boxes, scores, class_ids = [], [], []
        for y in self._tile_origins(height):
            for x in self._tile_origins(width):
                tile = np.ascontiguousarray(image[y:y + self.tile_size, x:x + self.tile_size])
                if not tile.any():  # entirely outside the drawn bbox
                    continue
                result = self.model.predict(
                    source=tile, conf=self.conf_min, imgsz=self.imgsz, device=self.device, verbose=False,
                )[0]
                if len(result.boxes) == 0:
                    continue
                boxes.append(result.boxes.xyxy.cpu() + torch.tensor([x, y, x, y], dtype=torch.float32))
                scores.append(result.boxes.conf.cpu())
                class_ids.append(result.boxes.cls.cpu().long())

        if not boxes:
            return {"type": "FeatureCollection", "features": []}

        boxes, scores, class_ids = torch.cat(boxes), torch.cat(scores), torch.cat(class_ids)
        # overlapping tiles see the same object twice; merge those per class
        keep = batched_nms(boxes, scores, class_ids, self.iou)
        boxes, scores, class_ids = boxes[keep].numpy(), scores[keep].numpy(), class_ids[keep].numpy()

        xs0, ys0 = xy(transform, boxes[:, 1], boxes[:, 0], offset="ul")
        xs1, ys1 = xy(transform, boxes[:, 3], boxes[:, 2], offset="ul")
        geoms = [shp_box(min(a, c), min(b, d), max(a, c), max(b, d)) for a, b, c, d in zip(xs0, ys0, xs1, ys1)]

        gdf = gpd.GeoDataFrame(
            {
                "score": scores.astype(float),
                "class_id": class_ids.astype(int),
                "class": [self.model.names[int(c)] for c in class_ids],
            },
            geometry=geoms,
            crs=crs,
        )
        gdf["area_m2"] = _area_m2(gdf)
        gdf = gdf.to_crs("EPSG:4326")

        logger.info(
            f"YOLO26 inference complete | {width}x{height} px at {transform.a:.2f} m | "
            f"{len(gdf)} detections | {time.time() - start:.2f}s"
        )
        return gdf.__geo_interface__
