import numpy as np
import torch
import rasterio
from rasterio.windows import Window
import matplotlib.pyplot as plt
from transformers import AutoImageProcessor, SegformerForSemanticSegmentation
from tqdm import tqdm
import geopandas as gpd
from rasterio.features import shapes
from shapely.geometry import shape
from rasterio.transform import from_bounds



class InferencePipeline:
    def __init__(self, model_id="restor/tcd-segformer-mit-b2"):
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"Segformer model is on device: {self.device} ---")
        self.processor = AutoImageProcessor.from_pretrained(model_id)
        self.model = SegformerForSemanticSegmentation.from_pretrained(model_id).to(self.device)
        self.model.eval()

    @staticmethod
    def _read_rgb(src:rasterio.DatasetReader, window=None, scale_16bit:bool =True) ->np.ndarray:
        # read rgb bands in satellite img.
        img = src.read([1,2,3], window=window)
        # Move channel axis to last dimension: (H, W, 3)
        img = np.moveaxis(img, 0, -1)
        if scale_16bit and img.dtype == np.uint16:
            img = (img / 256).astype(np.uint8)
        return img

    def get_full_mask(self,image_path):
        with rasterio.open(image_path) as src:
            # Sliced Inference
            h, w, patch_size = src.height, src.width, 512
            full_mask = np.zeros((h, w), dtype=np.uint8)
            # generate all windows covering the image with stride = 512
            windows = [(Window(x, y, min(patch_size, w-x), min(patch_size, h-y)), x, y)
                    for y in range(0, h, patch_size) for x in range(0, w, patch_size)]

            # testing prints
            print(f"starting tiled inference on {image_path}")
            # processing of each patches
            for window, x, y in tqdm(windows, desc="Inference...", unit="patch"):
                patch = self._read_rgb(src, window=window)
                # run model inference
                inputs = self.processor(images=patch, return_tensors="pt").to(self.device)
                with torch.no_grad():
                    logits = self.model(**inputs).logits
                #  upsampling back to full mask
                mask = torch.nn.functional.interpolate(logits, size=(window.height, window.width), mode="bilinear")
                full_mask[y:y+window.height, x:x+window.width] = (
                    mask.argmax(dim=1)[0].cpu().numpy() == 1
                ).astype(np.uint8)
            return full_mask


    @staticmethod
    def bbox_to_tree_geojson(bbox_coords, mask):
        min_lon, min_lat, max_lon, max_lat = bbox_coords
        height, width = mask.shape
        transform = from_bounds(min_lon, min_lat, max_lon, max_lat, width, height)
        results = []
        for geom, value in shapes(mask, mask=(mask == 1), transform=transform):
            results.append({
                "geometry": shape(geom),
                "properties": {"class": "tree", "area_m2": None}
            })
        if not results:
            return {"type": "FeatureCollection", "features": []}
        gdf = gpd.GeoDataFrame.from_features(results, crs="EPSG:4326")
        gdf_projected = gdf.to_crs("EPSG:3857")
        gdf["area_m2"] = gdf_projected.geometry.area
        return gdf 
