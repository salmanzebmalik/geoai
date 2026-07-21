from pathlib import Path
import time

import numpy as np
import torch
import rasterio
from PIL import Image

from app.utils.logger import get_logger
logger = get_logger(__name__)


class UNetTreePipeline:
    def __init__(self, weights_path: str | None = None, input_size: tuple = (64, 64),
                 threshold: float = 0.5):
        import segmentation_models_pytorch as smp  # lazy: keeps smp optional

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.input_size = input_size
        self.threshold = threshold

        self.model = smp.Unet(encoder_name="resnet50", encoder_weights=None,
                              in_channels=3, classes=1, activation=None)

        if weights_path is None:
            weights_path = Path(__file__).parent / "best_unet_tree_seg.pth"
        weights_path = Path(weights_path)
        if not weights_path.exists():
            raise FileNotFoundError(f"UNet tree weights not found at {weights_path}. Train with tree_crown_5m.ipynb.")

        self.model.load_state_dict(torch.load(weights_path, map_location=self.device))
        self.model.to(self.device).eval()
        logger.info(f"UNet tree weights loaded from {weights_path}")

    @torch.inference_mode()
    def get_full_mask_from_bytes(self, image_bytes: bytes) -> np.ndarray:
        start = time.time()
        with rasterio.MemoryFile(image_bytes) as memfile, memfile.open() as src:
            img = np.moveaxis(src.read([1, 2, 3]), 0, -1)  # (H, W, 3)
        orig_h, orig_w = img.shape[:2]
        if img.dtype == np.uint16:
            img = (img / 256).astype(np.uint8)

        img_pil = Image.fromarray(img).resize(self.input_size, Image.BICUBIC)
        x = np.array(img_pil).transpose(2, 0, 1).astype(np.float32) / 255.0
        x = torch.from_numpy(x).unsqueeze(0).to(self.device)

        prob = torch.sigmoid(self.model(x)).float().cpu().numpy().squeeze()  # (input_h, input_w)
        prob_pil = Image.fromarray((prob * 255).astype(np.uint8)).resize((orig_w, orig_h), Image.NEAREST)
        mask = ((np.array(prob_pil) / 255.0) > self.threshold).astype(np.uint8)
        logger.info(f"UNet inference complete | {time.time() - start:.2f}s")
        return mask
