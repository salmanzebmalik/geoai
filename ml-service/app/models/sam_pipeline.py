from pathlib import Path
import time

import numpy as np
import torch
from PIL import Image
from lang_sam import LangSAM  # https://github.com/luca-medeiros/lang-segment-anything.git
import contextlib
import io

# if torch.cuda.is_available():
#     torch.autocast(device_type="cuda", enabled=False).__enter__()

import rasterio
from rasterio.windows import Window
from typing import Optional

from app.models.model_downloader import ensure_langsam_models
from app.utils.tiling import tiled_mask


# Supress LangSAM internal noisy prints
import builtins
_original_print = builtins.print
builtins.print = lambda *args, **kwargs: None if args and isinstance(args[0], str) and (args[0].startswith("Predicting") or args[0].startswith("Predicted")) else _original_print(*args, **kwargs)

import warnings
warnings.filterwarnings("ignore", message="The given NumPy array is not writable") # this gets handled under the hood, so warning is just nosiy.

from app.utils.logger import get_logger
logger = get_logger(__name__)


class LangSAMPipeline:
    def __init__(self,patch_size: int = 1024,overlap: int = 128,device: Optional[str] = None,offline: bool = True,text_threshold: float = 0.15,box_threshold: float = 0.3):

        self.patch_size = patch_size
        self.overlap = overlap
        self.text_threshold = text_threshold
        self.box_threshold = box_threshold
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

        if offline:
            # set directory paths for local model files
            current_dir = Path(__file__).parent.resolve()
            model_dir = current_dir.parent / "models" / "local_langsam"
            ensure_langsam_models(model_dir)  # will download if missing (with lock)
            sam_ckpt_path = f"{model_dir}/sam2.1_hiera_large.pt"
            gdino_model_path = f"{model_dir}/groundingdino_hf_model"

            self.model = LangSAM(sam_type="sam2.1_hiera_large",sam_ckpt_path=sam_ckpt_path,gdino_model_ckpt_path=gdino_model_path,gdino_processor_ckpt_path=gdino_model_path,)
        else:  # online
            self.model = LangSAM()

    def _predict(self, patch: np.ndarray, keyword: str):
        with contextlib.redirect_stdout(io.StringIO()):   # LangSAM prints on every tile
            res = self.model.predict([Image.fromarray(patch)], [keyword],text_threshold=self.text_threshold, box_threshold=self.box_threshold)
        masks = res[0].get("masks") if res else None
        if masks is None or len(masks) == 0:
            return None

        m = masks.cpu().numpy() if hasattr(masks, "cpu") else np.asarray(masks)
        m = np.any(m, axis=0) if m.ndim == 3 else m
        th, tw = patch.shape[:2]
        if m.shape != (th, tw):
            m = np.array(Image.fromarray(m.astype(bool)).resize((tw, th), Image.NEAREST))
        return m

    def get_full_mask_from_bytes(self, image_bytes: bytes, keyword: str = "tree") -> np.ndarray:
        return tiled_mask(image_bytes, self.patch_size, self.overlap,
                          lambda p: self._predict(p, keyword), label="langsam")
