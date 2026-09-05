from pathlib import Path

import numpy as np
import torch
from app.utils.tiling import ndvi_mask, tiled_mask
from app.utils.logger import get_logger
logger = get_logger(__name__)

# Switching to Sentinel2_Resnet50_SI_MS only makes sense once that fetch also requests the other six bands
SATLAS_BACKBONE = "Sentinel2_Resnet50_SI_RGB" # uses rgb backbone


class SentinelSatlasTreePipeline:
    """Tree segmentation for 10m Sentinel-2 imagery. Same Satlas backbone as
    SatlasTreePipeline, fine-tuned on restor/tcd at 10m instead of 5m
    (see sentinel_satlas_tree_10m.ipynb) to match Sentinel-2's native GSD."""

    def __init__(self, weights_path: str | None = None, patch_size: int = 512, overlap: int = 64,
                 batch_size: int = 1, ndvi_threshold: float = 0.2):
        import satlaspretrain_models as spm  # lazy
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.patch_size = patch_size
        self.overlap = overlap
        self.batch_size = batch_size
        self.ndvi_threshold = ndvi_threshold
        self.model = spm.Weights().get_pretrained_model(SATLAS_BACKBONE, fpn=True, head=spm.Head.SEGMENT, num_categories=2, device=self.device)

        if weights_path is None:
            weights_path = Path(__file__).parent / "local_satlas_tree_sentinel" / "satlas_tree_sentinel.pt"
        weights_path = Path(weights_path)
        if not weights_path.exists():
            raise FileNotFoundError(f"Satlas Sentinel tree weights not found at {weights_path}. Train with sentinel_satlas_tree_10m.ipynb.")

        self.model.load_state_dict(torch.load(weights_path, map_location=self.device, mmap=True, weights_only=True))
        self.model.to(self.device).eval()
        logger.info(f"Satlas Sentinel tree weights loaded from {weights_path}")

    @torch.inference_mode()
    def _predict(self, patches: list[np.ndarray]) -> np.ndarray:
        t = torch.from_numpy(np.stack(patches)).permute(0, 3, 1, 2).float().to(self.device) / 255.0
        pred = self.model(t)[0]
        th, tw = patches[0].shape[:2]
        if pred.shape[-2:] != (th, tw):
            # edge tiles aren't always a multiple of the backbone's stride
            pred = torch.nn.functional.interpolate(pred, size=(th, tw), mode="bilinear")
        return (pred.argmax(1) == 1).cpu().numpy()

    def get_full_mask_from_bytes(self, image_bytes: bytes) -> np.ndarray:
        mask = tiled_mask(image_bytes, self.patch_size, self.overlap,
                          self._predict, label="satlas-sentinel", batch_size=self.batch_size)

        # drop anything the index says is not vegetation (water, roofs, roads,
        # bare soil); skipped when the crop has no NIR band
        vegetation = ndvi_mask(image_bytes, threshold=self.ndvi_threshold)
        if vegetation is not None:
            before = int(mask.sum())
            mask = np.logical_and(mask, vegetation).astype(np.uint8)
            logger.info(f"satlas-sentinel | ndvi>={self.ndvi_threshold} | {before} -> {int(mask.sum())} px")

        return mask
