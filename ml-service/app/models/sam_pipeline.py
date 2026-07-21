from pathlib import Path
import time

import numpy as np
import torch
from PIL import Image
from lang_sam import LangSAM  # https://github.com/luca-medeiros/lang-segment-anything.git


if torch.cuda.is_available():
    torch.autocast(device_type="cuda", enabled=False).__enter__()

import rasterio
from rasterio.windows import Window
from tqdm import tqdm
from typing import Optional
from app.models.model_downloader import ensure_langsam_models


# Supress LangSAM internal noisy prints
import builtins
_original_print = builtins.print
builtins.print = lambda *args, **kwargs: None if args and isinstance(args[0], str) and (args[0].startswith("Predicting") or args[0].startswith("Predicted")) else _original_print(*args, **kwargs)

import warnings
warnings.filterwarnings("ignore", message="The given NumPy array is not writable") # this gets handled under the hood, so warning is just nosiy.

from app.utils.logger import get_logger
logger = get_logger(__name__)


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

            self.model = LangSAM(
                sam_type="sam2.1_hiera_large",
                sam_ckpt_path=sam_ckpt_path,
                gdino_model_ckpt_path=gdino_model_path,
                gdino_processor_ckpt_path=gdino_model_path,
            )
        else:  # online
            self.model = LangSAM()

    def get_full_mask_from_bytes(self, image_bytes: bytes, keyword: str = "tree") -> np.ndarray:
        start_time = time.time()
        stride = self.patch_size - self.overlap
        with rasterio.MemoryFile(image_bytes) as memfile, memfile.open() as src:
            h, w = src.height, src.width
            logger.info(f"Image dimensions: {h}x{w}")

            full_mask = np.zeros((h, w), dtype=bool)

            # Calculate the total of tiles
            tiles_y = (h + stride - 1) // stride
            tiles_x = (w + stride - 1) // stride
            total_tiles = tiles_y * tiles_x
            logger.info(f"Processing {total_tiles} tiles")
            processed = 0
            failed = 0


            for y in range(0, h, stride):
                for x in range(0, w, stride):
                    th = min(self.patch_size, h - y)
                    tw = min(self.patch_size, w - x)
                    window = Window(x, y, tw, th)
                    try:
                        patch = src.read([1, 2, 3], window=window)
                        patch = np.moveaxis(patch, 0, -1)
                        patch = patch.copy() # ensure contiguous array for PIL
                        if patch.dtype == np.uint16:
                            patch = (patch >> 8).astype(np.uint8)
                        # Creates 
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
                        processed += 1
                    
                        # Log progress every 10%
                        if processed % max(1, total_tiles // 10) == 0:
                            logger.info(f"Progress: {processed}/{total_tiles} ({processed/total_tiles*100:.0f}%)")
                    except Exception as e:
                        failed += 1
                        logger.warning(f"Tile failed at ({x}, {y}): {str(e)}")
                        continue
            elapsed = time.time() - start_time
            logger.info(f"Inference complete ===> tiles: {processed}/{total_tiles} | failed: {failed} | time: {elapsed:.2f}s")
            return full_mask.astype(np.uint8)