import os
import requests
from huggingface_hub import snapshot_download


SAM2_CKPT_URLS = {
    "sam2.1_hiera_tiny": "https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_tiny.pt",
    "sam2.1_hiera_small": "https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_small.pt",
    "sam2.1_hiera_base_plus": "https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_base_plus.pt",
    "sam2.1_hiera_large": "https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_large.pt",
}


def download_langsam(local_path="ml-service/app/models/local_langsam", variant="sam2.1_hiera_large"):
    os.makedirs(local_path, exist_ok=True)

    if variant not in SAM2_CKPT_URLS:
        raise ValueError(f"Unknown SAM2 variant: {variant}")

    gdino_dir = os.path.join(local_path, "groundingdino_hf_model")
    if not os.path.exists(gdino_dir):
        print("Downloading GroundingDINO (once) from HF...")
        snapshot_download(
            repo_id="IDEA-Research/grounding-dino-base",
            local_dir=gdino_dir,
            local_dir_use_symlinks=False,
            resume_download=True,
        )
        print(f"GroundingDINO saved to: {gdino_dir}")

    ckpt_path = os.path.join(local_path, f"{variant}.pt")
    if not os.path.exists(ckpt_path):
        print(f"Downloading {variant} checkpoint...")
        response = requests.get(SAM2_CKPT_URLS[variant], stream=True)
        response.raise_for_status()
        with open(ckpt_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"{variant} checkpoint saved to: {ckpt_path}")

    bert_dir = os.path.join(local_path, "bert-base-uncased")
    if not os.path.exists(bert_dir):
        print("Downloading BERT processor files...")
        snapshot_download(
            repo_id="bert-base-uncased",
            local_dir=bert_dir,
            local_dir_use_symlinks=False,
            resume_download=True,
        )
        print(f"BERT processor files saved to: {bert_dir}")

    print(f"All files ready under {local_path}")


if __name__ == "__main__":
    download_langsam()
