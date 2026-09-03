import portalocker
from pathlib import Path
from typing import Optional

from .download_models.download_langsam import download_langsam
from .download_models.download_tcd import download_tcd


def ensure_langsam_models( model_dir: Path, force_download: bool = False,  # to refresh download
    timeout: int = 300, variant: str  ="sam2.1_hiera_large") -> None:
    required = [
        # model_dir / "sam2.1_hiera_large.pt",
        model_dir / f"{variant}.pt",
        model_dir / "groundingdino_hf_model",
        model_dir / "bert-base-uncased",
    ]
    if not force_download and model_dir.exists():
        if all(p.exists() for p in required):
            return

    lock_file = model_dir.parent / ".langsam_download.lock"
    with portalocker.Lock(lock_file, timeout=timeout):
        # double‑check inside the lock to avoid redundant downloads
        if not force_download and all(p.exists() for p in required):
            return

        # download
        print(f"Downloading LangSAM models to {model_dir}...")
        download_langsam(str(model_dir), variant=variant)
        print(f"LangSAM models ready")


def ensure_segformer_models( model_dir: Path, force_download: bool = False, timeout: int = 300):
    required = model_dir / "config.json"
    if not force_download and required.exists():
        return

    # use a file lock to prevent multiple processes from downloading
    lock_file = model_dir.parent / ".segformer_download.lock"
    with portalocker.Lock(lock_file, timeout=timeout):
        if not force_download and required.exists():
            return
        print(f"Downloading Segformer model to {model_dir}...")
        download_tcd(str(model_dir))
        print(f"Segformer model ready")
