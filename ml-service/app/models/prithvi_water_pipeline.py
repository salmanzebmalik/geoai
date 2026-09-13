from pathlib import Path

import numpy as np
import rasterio
import torch

from app.core.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

CHECKPOINT_NAME = "Prithvi-EO-V2-300M-TL-Sen1Floods11.pt"

# Sen1Floods11 chips are 512x512 at 10 m, so tiles of that size match the window
# the model was validated on. Any multiple of the ViT's patch size (16) runs,
# but 512 keeps the receptive-field context consistent with training.
PATCH_SIZE = 512

# The fine-tune config sets use_metadata: false, so the head was trained with
# both coordinate inputs as None.
TEMPORAL_COORDS = None
LOCATION_COORDS = None

# Sentinel-2 L2A DN -> reflectance, matching constant_scale in the model config.
REFLECTANCE_SCALE = 10000.0

WATER_CLASS = 1


class PrithviWaterPipeline:
    """Water / flood segmentation on 6-band Sentinel-2 L2A.

    Prithvi-EO-2.0-300M-TL fine-tuned on Sen1Floods11. Expects the crop the
    sentinel bbox path writes for model_type 'water_prithvi': bands 1-6 are
    B02 B03 B04 B8A B11 B12, raw uint16 reflectance at 10 m, no rescale.
    """

    def __init__(self, model_dir: str | None = None, patch_size: int = PATCH_SIZE):
        from terratorch.cli_tools import LightningInferenceModel  # lazy
        from terratorch.datamodules.sen1floods11 import MEANS, STDS

        model_dir = Path(model_dir or settings.prithvi_model_dir)
        config_path = model_dir / "config.yaml"
        weights_path = model_dir / CHECKPOINT_NAME

        for path in (config_path, weights_path):
            if not path.exists():
                raise FileNotFoundError(
                    f"Prithvi water model not found at {path}. Download it with "
                    f"'hf download ibm-nasa-geospatial/Prithvi-EO-2.0-300M-TL-Sen1Floods11 "
                    f"--local-dir {model_dir}'."
                )

        self.patch_size = patch_size
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        lit = LightningInferenceModel.from_config(str(config_path), str(weights_path))
        # from_config leaves the weights on CPU regardless of the trainer banner
        self.net = lit.model.to(self.device).eval()

        # The config's test_transform is ToTensorV2 alone, so standardising here
        # with the datamodule's own per-band constants is the whole of it.
        self.bands = list(lit.datamodule.bands)
        self.mean = torch.tensor([MEANS[b] for b in self.bands], dtype=torch.float32).view(-1, 1, 1).to(self.device)
        self.std = torch.tensor([STDS[b] for b in self.bands], dtype=torch.float32).view(-1, 1, 1).to(self.device)

        logger.info(
            f"Prithvi water weights loaded from {weights_path} onto {self.device} | bands {self.bands}"
        )

    @torch.inference_mode()
    def _predict_tile(self, tile: np.ndarray) -> np.ndarray:
        """`tile` is (C, H, W) reflectance on 0-1; returns (H, W) class indices."""
        x = torch.from_numpy(np.ascontiguousarray(tile)).to(self.device)
        x = (x - self.mean) / self.std
        out = self.net(
            x.unsqueeze(0),
            temporal_coords=TEMPORAL_COORDS,
            location_coords=LOCATION_COORDS,
        )
        return out.output.argmax(dim=1)[0].cpu().numpy()

    def get_full_mask_from_bytes(self, image_bytes: bytes) -> np.ndarray:
        with rasterio.MemoryFile(image_bytes) as mem, mem.open() as src:
            if src.count < len(self.bands):
                raise ValueError(
                    f"Prithvi water needs {len(self.bands)} bands "
                    f"(B02 B03 B04 B8A B11 B12), got {src.count}. "
                    "The crop was fetched for a different model."
                )
            image = src.read(indexes=list(range(1, len(self.bands) + 1)))

        data = image.astype(np.float32) / REFLECTANCE_SCALE

        height, width = data.shape[-2:]
        pad_h = (self.patch_size - height % self.patch_size) % self.patch_size
        pad_w = (self.patch_size - width % self.patch_size) % self.patch_size
        if pad_h or pad_w:
            data = np.pad(data, ((0, 0), (0, pad_h), (0, pad_w)), mode="reflect")

        padded_h, padded_w = data.shape[-2:]
        mask = np.zeros((padded_h, padded_w), dtype=np.uint8)

        tiles = 0
        for y in range(0, padded_h, self.patch_size):
            for x in range(0, padded_w, self.patch_size):
                window = data[:, y:y + self.patch_size, x:x + self.patch_size]
                mask[y:y + self.patch_size, x:x + self.patch_size] = self._predict_tile(window)
                tiles += 1

        mask = (mask[:height, :width] == WATER_CLASS).astype(np.uint8)

        logger.info(
            f"prithvi-water | {height}x{width} | {tiles} tiles | "
            f"{int(mask.sum())} water px ({100.0 * mask.mean():.2f}%)"
        )
        return mask
