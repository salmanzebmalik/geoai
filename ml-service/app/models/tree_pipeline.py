from pathlib import Path
from typing import Optional

import numpy as np
import torch
from rasterio.windows import Window
from transformers import AutoImageProcessor, SegformerForSemanticSegmentation
from tqdm import tqdm
from app.models.model_downloader import ensure_segformer_models

from app.utils.logger import get_logger
logger = get_logger(__name__)
from app.utils.tiling import read_rgb, tiled_mask

class TCDSegformer:
    def __init__(self,model_id="restor/tcd-segformer-mit-b2",offline: bool = True,patch_size: int = 1024,overlap: int = 128,batch_size: int = 8,):

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
        self.batch_size = batch_size
        self.model.eval()



    @torch.inference_mode()
    def _predict(self, patches: list[np.ndarray]) -> np.ndarray:
        inputs = self.processor(images=patches, return_tensors="pt").to(self.device)
        with torch.autocast(device_type=self.device):
            logits = self.model(**inputs).logits
        up = torch.nn.functional.interpolate(logits, size=patches[0].shape[:2], mode="bilinear")
        return (up.argmax(1) == 1).cpu().numpy()

    def get_full_mask_from_bytes(self, image_bytes: bytes) -> np.ndarray:
        return tiled_mask(image_bytes, self.patch_size, self.overlap,
                          self._predict, label="segformer", batch_size=self.batch_size)