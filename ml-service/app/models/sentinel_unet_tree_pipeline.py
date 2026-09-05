from pathlib import Path
import time

import numpy as np
import torch
import rasterio
from PIL import Image

from app.utils.logger import get_logger
from app.utils.tiling import read_rgb
logger = get_logger(__name__)


class SentinelUNetTreePipeline:
    """Tree segmentation for 10m RGB Sentinel-2 imagery. Same resnet50 UNet
    architecture as UNetTreePipeline, retrained on restor/tcd downsampled to
    10m/pixel(see sentinel_tree_crown_10m.ipynb) to match
    Sentinel-2's native GSD"""

    def __init__(self, weights_path: str | None = None, input_size: tuple = (64, 64),
                 threshold: float = 0.5):
        import segmentation_models_pytorch as smp  # lazy: keeps smp optional

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.input_size = input_size
        self.threshold = threshold

        self.model = smp.Unet(encoder_name="resnet50", encoder_weights=None,
                              in_channels=3, classes=1, activation=None)

        if weights_path is None:
            weights_path = Path(__file__).parent / "local_unet" / "best_unet_tree_seg_sentinel.pth"
        weights_path = Path(weights_path)
        if not weights_path.exists():
            raise FileNotFoundError(f"UNet Sentinel tree weights not found at {weights_path}. Train with sentinel_tree_crown_10m.ipynb.")

        self.model.load_state_dict(torch.load(weights_path, map_location=self.device, mmap=True, weights_only=True))
        self.model.to(self.device).eval()
        logger.info(f"UNet Sentinel tree weights loaded from {weights_path}")

    @torch.inference_mode()
    def get_full_mask_from_bytes(self, image_bytes: bytes) -> np.ndarray:
        t0 = time.time()
        with rasterio.MemoryFile(image_bytes) as mem, mem.open() as src:
            img = read_rgb(src)
        h, w = img.shape[:2]

        small = np.asarray(Image.fromarray(img).resize(self.input_size, Image.BICUBIC))
        x = torch.from_numpy(small.transpose(2, 0, 1).astype(np.float32) / 255.0)
        prob = torch.sigmoid(self.model(x.unsqueeze(0).to(self.device)))
        prob = prob.float().cpu().numpy().squeeze()

        prob = np.asarray(
            Image.fromarray((prob * 255).astype(np.uint8)).resize((w, h), Image.NEAREST)
        ) / 255.0
        mask = (prob > self.threshold).astype(np.uint8)
        logger.info(f"unet-sentinel | {h}x{w} | {time.time() - t0:.1f}s")
        return mask
