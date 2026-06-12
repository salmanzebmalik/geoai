from pathlib import Path

import numpy as np
import torch
from PIL import Image
from lang_sam import LangSAM  # https://github.com/luca-medeiros/lang-segment-anything.git
import rasterio
from rasterio.windows import Window
from rasterio.features import shapes
from shapely.geometry import shape
from rasterio.transform import from_bounds
import geopandas as gpd
from tqdm import tqdm
from typing import Optional, Tuple, List
from app.models.model_downloader import ensure_langsam_models


class LangSAMPipeline:
    def __init__(
        self,
        patch_size: int = 1024,
        overlap: int = 128,
        device: Optional[str] = None,
        offline: bool = True,
        # confidence thresholds for LangSAM predictions --- need to tune
        text_threshold: float = 0.15,
        box_threshold: float = 0.3
    ):
        self.patch_size = patch_size
        self.overlap = overlap
        self.text_threshold = text_threshold
        self.box_threshold = box_threshold
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        if offline:
            # set directory paths for local model files
            current_dir = Path(__file__).parent.resolve()
            model_dir = current_dir.parent / "models" / "local_langsam"

            ensure_langsam_models(model_dir)  # will download if missing (with lock)

            sam_ckpt_path = f"{model_dir}/sam2.1_hiera_large.pt"
            gdino_model_path = f"{model_dir}/groundingdino_hf_model"
            gdino_processor_path = f"{model_dir}/bert-base-uncased"

            self.model = LangSAM(
                sam_type="sam2.1_hiera_large",
                sam_ckpt_path=sam_ckpt_path,
                gdino_model_ckpt_path=gdino_model_path,
                gdino_processor_ckpt_path=gdino_processor_path,
            )
        else:  # online
            self.model = LangSAM()

    def get_full_mask_from_bytes(self, image_bytes: bytes, keyword: str = "tree") -> np.ndarray:
        stride = self.patch_size - self.overlap
        with rasterio.MemoryFile(image_bytes) as memfile, memfile.open() as src:
            h, w = src.height, src.width
            full_mask = np.zeros((h, w), dtype=bool)
            for y in range(0, h, stride):
                for x in range(0, w, stride):
                    th = min(self.patch_size, h - y)
                    tw = min(self.patch_size, w - x)
                    window = Window(x, y, tw, th)
                    patch = src.read([1, 2, 3], window=window)
                    patch = np.moveaxis(patch, 0, -1)
                    if patch.dtype == np.uint16:
                        patch = (patch >> 8).astype(np.uint8)
                    try:
                        res = self.model.predict(
                            [Image.fromarray(patch)],
                            [keyword],
                            text_threshold=self.text_threshold,
                            box_threshold=self.box_threshold,
                        )
                        masks = res[0].get("masks") if res else None
                        if masks is not None and len(masks) > 0:
                            m_np = masks.cpu().numpy().copy() if hasattr(masks, "cpu") else masks
                            if m_np.ndim == 3:
                                c_mask = np.any(m_np, axis=0)
                            else:
                                c_mask = m_np
                            if c_mask.shape != (th, tw):
                                c_mask = np.array(Image.fromarray(c_mask).resize((tw, th), Image.NEAREST))
                            full_mask[y:y+th, x:x+tw] |= c_mask.astype(bool)
                    except Exception as e:
                        print(f"Skipping tile at ({x}, {y}): {e}")
            return full_mask.astype(np.uint8)

    @staticmethod
    def bbox_to_tree_geojson(bbox_coords, mask) -> gpd.GeoDataFrame:
        min_lon, min_lat, max_lon, max_lat = bbox_coords
        height, width = mask.shape
        transform = from_bounds(min_lon, min_lat, max_lon, max_lat, width, height)
        results = []
        for geom, value in shapes(mask.astype(np.uint8), mask=(mask == 1), transform=transform):
            results.append(
                {
                    "geometry": shape(geom),
                    "properties": {"class": "tree", "area_m2": None},
                }
            )
        if not results:
            return gpd.GeoDataFrame({"geometry": []}, crs="EPSG:4326")
        gdf = gpd.GeoDataFrame.from_features(results, crs="EPSG:4326")
        gdf_projected = gdf.to_crs("EPSG:3857")
        gdf["area_m2"] = gdf_projected.geometry.area
        gdf = gdf.drop(columns=["geometry"]).set_geometry(gdf_projected.geometry)  # keep projected?
        gdf["area_m2"] = gdf_projected.geometry.area
        return gdf
