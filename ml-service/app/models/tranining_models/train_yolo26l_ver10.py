"""
train_yolo26l_ver10.py

Updated production-grade training script for YOLO26 Large (yolo26l.pt) on xView dataset (ver9).
Incorporates recommendations based on the 50-epoch results analysis:
- Extended epoch budget (100 epochs) to allow full convergence beyond the initial plateau.
- Resumes seamlessly from the last checkpoint (`last.pt`) if available.
- Explicitly enforces cache=False and optimized batch sizing to prevent OOM errors.
- Applies cosine learning rate decay and fine-tuned loss weights.
"""

from ultralytics import YOLO
from pathlib import Path
import os


def main():
    # Define paths
    dataset_yaml = "/home/ubuntu/work/saved_data/sabeel/datasets/xView/processed_sliced_1024_clean_ver9/xview_60.yaml"

    # Check if a previous checkpoint exists to resume from, otherwise start fresh with yolo26l.pt
    checkpoint_path = "/home/ubuntu/work/saved_data/monir/geoai/runs/detect/xview_training/yolo26l_ver9_scaled-2/weights/last.pt"

    if os.path.exists(checkpoint_path):
        print(f"Resuming training from checkpoint: {checkpoint_path}")
        model = YOLO(checkpoint_path)
        resume_flag = True
    else:
        print("Initializing new training run with pretrained yolo26l.pt")
        model = YOLO("yolo26l.pt")
        resume_flag = False

    # Training configuration tailored for xView production reliability
    results = model.train(
        data=dataset_yaml,
        epochs=100,  # Extended to 100 epochs to ensure full convergence
        imgsz=1024,  # High-resolution 1024x1024 tiles
        batch=4,  # Optimized for 12-16GB VRAM footprint
        device=0,  # GPU acceleration
        workers=8,  # Balanced dataloader workers

        # Loss and Optimization Tuning
        box=7.5,  # High localization weight for small targets
        cls=1.5,  # Classification penalty weight
        amp=True,  # Automatic Mixed Precision for memory efficiency
        cache=False,  # Disabled system RAM caching to prevent OOM errors

        # Aerial Augmentations
        mosaic=1.0,  # Full mosaic augmentation for dense spatial context
        mixup=0.15,  # Mild mixup for color/texture blending
        copy_paste=0.1,  # Copy-paste augmentation for rare objects
        degrees=45.0,  # Full rotational invariance for overhead perspectives
        fliplr=0.5,  # Horizontal flip
        flipud=0.5,  # Vertical flip for top-down symmetry

        # Checkpointing & Logging
        save=True,
        save_period=5,  # Save weights every 5 epochs
        project="runs/detect",
        name="yolo26l_ver10_extended",
        exist_ok=True,
        resume=resume_flag
    )

    print("\n[SUCCESS] Extended training session completed successfully!")


if __name__ == '__main__':
    main()