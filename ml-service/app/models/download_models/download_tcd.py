import os
from transformers import SegformerForSemanticSegmentation, AutoImageProcessor


def download_tcd(local_path="ml-service/app/models/local_tcd-segformer_local"):
    # Local folder name
    LOCAL_MODEL_DIR = local_path
    os.makedirs(LOCAL_MODEL_DIR, exist_ok=True)
    print("Downloading Segformer model and processor from HF")
    model = SegformerForSemanticSegmentation.from_pretrained("restor/tcd-segformer-mit-b2")
    processor = AutoImageProcessor.from_pretrained("restor/tcd-segformer-mit-b2")

    # Save to local directory
    model.save_pretrained(LOCAL_MODEL_DIR)
    processor.save_pretrained(LOCAL_MODEL_DIR)

    print("downloaded Segformer model and processor saved to:", LOCAL_MODEL_DIR)


# In case run manually
if __name__ == "__main__":
    download_tcd()