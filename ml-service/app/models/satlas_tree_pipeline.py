from pathlib import Path
import time

import numpy as np
import torch
import rasterio
from rasterio.windows import Window

from app.utils.logger import get_logger
logger = get_logger(__name__)

SATLAS_BACKBONE = "Sentinel2_Resnet50_SI_RGB"  # reputable Allen AI backbone, RGB


class SatlasTreePipeline:
    """Tree segmentation for 5m RGB satellite imagery. SATLAS backbone + a head
    fine-tuned on tcd@~5m (see satlas_tree_5m.ipynb) """

    def __init__(self, weights_path: str | None = None, patch_size: int = 512, overlap: int = 64):
        import satlaspretrain_models as spm  # lazy
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.patch_size = patch_size
        self.overlap = overlap

        self.model = spm.Weights().get_pretrained_model(
            SATLAS_BACKBONE, fpn=True, head=spm.Head.SEGMENT, num_categories=2, device=self.device
        )

        if weights_path is None:
            weights_path = Path(__file__).parent / "local_satlas_tree" / "satlas_tree.pt"
        weights_path = Path(weights_path)
        if not weights_path.exists():
            raise FileNotFoundError(f"Satlas tree weights not found at {weights_path}. Train with satlas_tree_5m.ipynb.")

        self.model.load_state_dict(torch.load(weights_path, map_location=self.device))
        self.model.to(self.device).eval()
        logger.info(f"Satlas tree weights loaded from {weights_path}")

    @torch.inference_mode()
    def get_full_mask_from_bytes(self, image_bytes: bytes) -> np.ndarray:
        stride = self.patch_size - self.overlap
        start = time.time()
        with rasterio.MemoryFile(image_bytes) as memfile, memfile.open() as src:
            h, w = src.height, src.width
            full_mask = np.zeros((h, w), dtype=np.uint8)
            for y in range(0, h, stride):
                for x in range(0, w, stride):
                    th, tw = min(self.patch_size, h - y), min(self.patch_size, w - x)
                    patch = src.read([1, 2, 3], window=Window(x, y, tw, th))
                    patch = np.moveaxis(patch, 0, -1)
                    if patch.dtype == np.uint16:
                        patch = (patch / 256).astype(np.uint8)
                    t = torch.from_numpy(patch).permute(2, 0, 1).float().unsqueeze(0).to(self.device) / 255.0
                    pred = self.model(t)[0]
                    full_mask[y:y + th, x:x + tw] = (pred.argmax(1)[0].cpu().numpy() == 1).astype(np.uint8)
            logger.info(f"Satlas inference complete | {time.time() - start:.2f}s")
            return full_mask
