import os
import requests
from huggingface_hub import snapshot_download
from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor
from transformers import AutoProcessor


def download_langsam(local_path="ml-service/app/models/local_langsam"):
    # Create a CACHE directory
    # local_path
    os.makedirs(local_path, exist_ok=True)


    # SAM 2 Variant based on this file: https://github.com/luca-medeiros/lang-segment-anything/blob/main/lang_sam/models/sam.py
    SAM2_VARIANT = "sam2.1_hiera_large"   # or "sam2.1_hiera_small", "sam2.1_hiera_base_plus", "sam2.1_hiera_large"


    gdino_dir = os.path.join(local_path, "groundingdino_hf_model")
    print("Downloading GroundingDINO (once) from HF...")
    snapshot_download(
        repo_id="IDEA-Research/grounding-dino-base",
        local_dir=gdino_dir,
        local_dir_use_symlinks=False,
        resume_download=True,
    )
    print(f"GroundingDINO saved to: {gdino_dir}")



    # Download SAM Model checkpoints
    # https://github.com/facebookresearch/segment-anything?tab=readme-ov-file
    # SAM 2 Variant based on this file: https://github.com/luca-medeiros/lang-segment-anything/blob/main/lang_sam/models/sam.py
    if SAM2_VARIANT == "sam2.1_hiera_tiny":
        ckpt_url = "https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_tiny.pt"
    elif SAM2_VARIANT == "sam2.1_hiera_small":
        ckpt_url = "https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_small.pt"
    elif SAM2_VARIANT == "sam2.1_hiera_base_plus":
        ckpt_url = "https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_base_plus.pt"
    elif SAM2_VARIANT == "sam2.1_hiera_large":
        ckpt_url = "https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_large.pt"
    else:
        raise ValueError("Unknown SAM2 variant")

    ckpt_path = os.path.join(local_path, f"{SAM2_VARIANT}.pt")

    print(f"Downloading {SAM2_VARIANT} checkpoint...")
    resp = requests.get(ckpt_url, stream=True)
    with open(ckpt_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)


    print("Downloading BERT processor files...")
    snapshot_download(
        repo_id="bert-base-uncased",
        local_dir=os.path.join(local_path, "bert-base-uncased"),
        local_dir_use_symlinks=False,
        resume_download=True,
    )
    print("BERT processor files downloaded and saved to:", os.path.join(local_path, "bert-base-uncased"))

    print(f"All files saved under {local_path}")


if __name__ == "__main__":
    download_langsam()
