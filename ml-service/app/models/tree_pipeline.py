import os
from pathlib import Path
import sys
from typing import Optional

import numpy as np
import torch
import rasterio
from rasterio.windows import Window
from transformers import AutoImageProcessor, SegformerForSemanticSegmentation
from tqdm import tqdm
from app.models.model_downloader import ensure_segformer_models

from app.utils.logger import get_logger
logger = get_logger(__name__)
import time


class TCDSegformer:
    def __init__(
        self,
        model_id="restor/tcd-segformer-mit-b2",
        offline: bool = True,
        patch_size: int = 1024,
        overlap: int = 128,
    ):

        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        if offline:
            # look for local models in this path, if not exists, raise error
            current_dir = Path(__file__).parent.resolve()
            model_dir = current_dir.parent / "models" / "local_tcd-segformer_local"
            ensure_segformer_models(model_dir)  # will download if missing, with lock

            if not model_dir.exists():
                raise FileNotFoundError(f"TCD Segformer model not found at {model_dir}")

            self.processor = AutoImageProcessor.from_pretrained(str(model_dir), local_files_only=True)
            self.model = SegformerForSemanticSegmentation.from_pretrained(str(model_dir), local_files_only=True).to(self.device)
            logger.info("TCD Segformer model weights loaded from local files")
        else:
            self.processor = AutoImageProcessor.from_pretrained(model_id)
            self.model = SegformerForSemanticSegmentation.from_pretrained(model_id).to(self.device)

        self.patch_size = patch_size
        self.overlap = overlap
        self.model.eval()



    @staticmethod
    def _read_rgb(
        src: rasterio.DatasetReader, window=None, scale_16bit: bool = True
    ) -> np.ndarray:
        # read rgb bands in satellite img.
        img = src.read([1, 2, 3], window=window)
        # Move channel axis to last dimension: (H, W, 3)
        img = np.moveaxis(img, 0, -1)
        if scale_16bit and img.dtype == np.uint16:
            img = (img / 256).astype(np.uint8)
        return img

    def get_full_mask(self, image_path: str) -> np.ndarray:
        with rasterio.open(image_path) as src:
            # Sliced Inference
            h, w = src.height, src.width
            full_mask = np.zeros((h, w), dtype=np.uint8)
            # generate all windows covering the image with stride = 512
            windows = [(Window(x, y, min(self.patch_size, w - x), min(self.patch_size, h - y)), x, y,)
                       for y in range(0, h, self.patch_size)
                       for x in range(0, w, self.patch_size)
                       ]

            # processing of each patches
            for window, x, y in tqdm(windows, desc="Inference...", unit="patch"):
                patch = self._read_rgb(src, window=window)
                # run model inference
                inputs = self.processor(images=patch, return_tensors="pt").to(self.device)
                with torch.no_grad():
                    logits = self.model(**inputs).logits
                #  upsampling back to full mask
                mask = torch.nn.functional.interpolate(logits, size=(window.height, window.width), mode="bilinear")
                full_mask[y: y + window.height, x: x + window.width] = (mask.argmax(dim=1)[0].cpu().numpy() == 1).astype(np.uint8)
            return full_mask

    def get_full_mask_from_bytes(self, image_bytes: bytes) -> np.ndarray:
        """same as get_full_mask but accepts bytes"""
        stride = self.patch_size - self.overlap
        logger.info(f"Reading image... | size: {len(image_bytes)} bytes")
        start_time = time.time()
        with rasterio.MemoryFile(image_bytes) as memfile:  # only line changing
            with memfile.open() as src:
                h, w = src.height, src.width
                logger.info(f"Image dimensions: {h}x{w}")
                full_mask = np.zeros((h, w), dtype=np.uint8)



                windows = [
                    (
                        Window(
                            x,
                            y,
                            min(self.patch_size, w - x),
                            min(self.patch_size, h - y),
                        ),
                        x,
                        y,
                    )
                    # subtract overlap from patch size to get step size that overlaps
                    for y in range(0, h, stride) 
                    for x in range(0, w, stride)
                ]

                total_tiles = len(windows)
                # logger init
                logger.info("Processing tiles -- Total tile length: %d", total_tiles)
                processed = 0
                failed = 0
                for window, x, y in windows:
                    try:
                        patch = self._read_rgb(src, window=window)
                        inputs = self.processor(images=patch, return_tensors="pt").to(self.device)
                        with torch.inference_mode(), torch.autocast(device_type=self.device):
                            logits = self.model(**inputs).logits
                        mask = torch.nn.functional.interpolate(logits, size=(window.height, window.width), mode="bilinear")
                        full_mask[y: y + window.height, x: x + window.width] = (mask.argmax(dim=1)[0].cpu().numpy() == 1).astype(np.uint8)
                        processed += 1
                        # Log progress every 10%
                        if processed % max(1, total_tiles // 10) == 0:
                            logger.info(f"Progress: {processed}/{total_tiles} ({processed/total_tiles*100:.0f}%)")
                    # Final summary
                    except Exception as e:
                        logger.warning(f"Failed to process tile at ({x}, {y}): {e}")
                        failed += 1
                        continue
                elapsed = time.time() - start_time
                logger.info(f"Inference complete | tiles: {processed}/{total_tiles} | failed: {failed} | time: {elapsed:.2f}s")
                return full_mask
