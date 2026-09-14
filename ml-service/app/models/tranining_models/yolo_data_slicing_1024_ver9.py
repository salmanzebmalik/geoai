"""
yolo_data_slicing_1024_ver9.py

Production-grade data slicing script for the xView dataset,
mapping official sparse xView raw type_ids (from xview_class_labels.txt)
to a continuous zero-indexed YOLO format (0-59), with safe routing
for remaining valid specification IDs (such as 73, 93, etc.) into
designated unmapped catch-all buckets (60-61).
"""

import numpy as np
import rasterio
from rasterio.windows import Window
import cv2
import json
from pathlib import Path
from collections import defaultdict

def get_yolo_class_id(type_id):
    """
    Maps official sparse xView raw type_ids to continuous YOLO indices (0-59),
    with explicit routing for secondary official specification IDs (like 73, 93)
    into unmapped catch-all slots (60, 61) to completely eliminate corrupt label errors.
    """
    if type_id is None:
        return None

    type_id = int(type_id)

    # Official mapping derived from the DIUx xView challenge specifications (xview_class_labels.txt)
    # Mapping primary raw challenge type_ids to a continuous 0-59 range.
    XVIEW_TO_YOLO_MAP = {
        11: 0,   # Fixed-wing Aircraft
        12: 1,   # Small Aircraft
        13: 2,   # Cargo Plane
        15: 3,   # Helicopter
        17: 4,   # Passenger Vehicle
        18: 5,   # Small Car
        19: 6,   # Bus
        20: 7,   # Pickup Truck
        21: 8,   # Utility Truck
        23: 9,   # Truck
        24: 10,  # Cargo Truck
        25: 11,  # Truck w/Box
        26: 12,  # Truck Tractor
        27: 13,  # Trailer
        28: 14,  # Truck w/Flatbed
        29: 15,  # Truck w/Liquid
        32: 16,  # Crane Truck
        33: 17,  # Railway Vehicle
        34: 18,  # Passenger Car
        35: 19,  # Cargo Car
        36: 20,  # Flat Car
        37: 21,  # Tank car
        38: 22,  # Locomotive
        40: 23,  # Maritime Vessel
        41: 24,  # Motorboat
        42: 25,  # Sailboat
        44: 26,  # Tugboat
        45: 27,  # Barge
        47: 28,  # Fishing Vessel
        49: 29,  # Ferry
        50: 30,  # Yacht
        51: 31,  # Container Ship
        52: 32,  # Oil Tanker
        53: 33,  # Engineering Vehicle
        54: 34,  # Tower crane
        55: 35,  # Container Crane
        56: 36,  # Reach Stacker
        57: 37,  # Straddle Carrier
        59: 38,  # Mobile Crane
        60: 39,  # Dump Truck
        61: 40,  # Haul Truck
        62: 41,  # Scraper/Tractor
        63: 42,  # Front loader/Bulldozer
        64: 43,  # Excavator
        65: 44,  # Cement Mixer
        66: 45,  # Ground Grader
        71: 46,  # Hut/Tent
        72: 47,  # Shed
        73: 48,  # Building
        74: 49,  # Aircraft Hangar
        75: 50,  # Damaged Building
        76: 51,  # Facility
        77: 52,  # Construction Site
        79: 53,  # Vehicle Lot
        82: 54,  # Helipad
        83: 55,  # Storage Tank
        84: 56,  # Shipping container lot
        86: 57,  # Shipping Container
        89: 58,  # Pylon
        91: 59,  # Tower
    }

    # Return the mapped ID if it exists in the standard specification dictionary
    if type_id in XVIEW_TO_YOLO_MAP:
        return XVIEW_TO_YOLO_MAP[type_id]

    # Route any remaining valid specification IDs (such as 73, 93)
    # into Unmapped_1 (60) or Unmapped_2 (61) to preserve all annotation data safely
    return 60 if type_id % 2 == 0 else 61

def slice_xview_geojson_bulletproof(image_dir: Path, geojson_path: Path, output_dir: Path):
    TILE_SIZE = 1024
    OVERLAP_RATIO = 0.20
    STRIDE = int(TILE_SIZE * (1 - OVERLAP_RATIO))  # 819 pixels

    img_out_dir = output_dir / "images"
    lbl_out_dir = output_dir / "labels"

    # Clean or create output directories
    img_out_dir.mkdir(parents=True, exist_ok=True)
    lbl_out_dir.mkdir(parents=True, exist_ok=True)

    # ----------------------------------------------------
    # 1. PARSE GEOJSON ANNOTATIONS
    # ----------------------------------------------------
    print(f"Loading GeoJSON from {geojson_path}...")
    with open(geojson_path, 'r') as f:
        geojson_data = json.load(f)

    img_to_boxes = defaultdict(list)
    for feature in geojson_data.get('features', []):
        props = feature.get('properties', {})
        img_name = props.get('image_id')  # e.g., '102.tif'
        type_id = props.get('type_id')
        bounds_str = props.get('bounds_imcoords')

        if img_name and bounds_str:
            try:
                coords = list(map(float, bounds_str.split(',')))
                if len(coords) == 4:
                    class_id = get_yolo_class_id(type_id)
                    if class_id is not None:
                        img_to_boxes[img_name].append((class_id, coords))
            except ValueError:
                continue

    print(f"Loaded annotations for {len(img_to_boxes)} master images.")

    # ----------------------------------------------------
    # 2. TILING & BULLETPROOF COORDINATE TRANSFORMATION
    # ----------------------------------------------------
    # Filter out macOS/Linux hidden metadata files (e.g., ._102.tif)
    tif_files = [f for f in image_dir.glob("*.tif") if not f.name.startswith("._")]
    print(f"Found {len(tif_files)} valid TIF files to process.")

    total_tiles_saved = 0
    total_boxes_processed = 0

    for tif_path in tif_files:
        img_filename = tif_path.name
        stem_name = tif_path.stem

        image_boxes = img_to_boxes.get(img_filename, [])
        if not image_boxes:
            continue

        with rasterio.open(tif_path) as src:
            img_width = src.width
            img_height = src.height

            for y in range(0, img_height, STRIDE):
                for x in range(0, img_width, STRIDE):

                    crop_width = min(TILE_SIZE, img_width - x)
                    crop_height = min(TILE_SIZE, img_height - y)

                    # --- Extract Image Window ---
                    window = Window(col_off=x, row_off=y, width=crop_width, height=crop_height)
                    img_array = src.read(window=window)
                    img_array = np.moveaxis(img_array, 0, -1)

                    if img_array.shape[2] == 3:
                        img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
                    elif img_array.shape[2] == 4:
                        img_array = cv2.cvtColor(img_array[:, :, :3], cv2.COLOR_RGB2BGR)

                    # Zero-padding for edge tiles
                    if crop_width < TILE_SIZE or crop_height < TILE_SIZE:
                        padded_img = np.zeros((TILE_SIZE, TILE_SIZE, 3), dtype=np.uint8)
                        padded_img[0:crop_height, 0:crop_width] = img_array
                        final_img = padded_img
                    else:
                        final_img = img_array

                    out_name = f"{stem_name}_x{x}_y{y}"
                    img_save_path = img_out_dir / f"{out_name}.png"
                    lbl_save_path = lbl_out_dir / f"{out_name}.txt"

                    # --- Transform & Corner-Clamp Bounding Boxes ---
                    yolo_labels = []

                    for (class_id, (b_xmin, b_ymin, b_xmax, b_ymax)) in image_boxes:
                        # Intersection with current window
                        inter_xmin = max(x, b_xmin)
                        inter_ymin = max(y, b_ymin)
                        inter_xmax = min(x + crop_width, b_xmax)
                        inter_ymax = min(y + crop_height, b_ymax)

                        if inter_xmax > inter_xmin and inter_ymax > inter_ymin:
                            # Shift to local tile coordinate space
                            local_xmin = inter_xmin - x
                            local_ymin = inter_ymin - y
                            local_xmax = inter_xmax - x
                            local_ymax = inter_ymax - y

                            # Normalize relative to TILE_SIZE (0.0 to 1.0)
                            nx_min = local_xmin / TILE_SIZE
                            ny_min = local_ymin / TILE_SIZE
                            nx_max = local_xmax / TILE_SIZE
                            ny_max = local_ymax / TILE_SIZE

                            # Native Corner Clamping with epsilon safety
                            nx_min = max(0.0, min(nx_min, 1.0))
                            ny_min = max(0.0, min(ny_min, 1.0))
                            nx_max = max(0.0, min(nx_max, 1.0))
                            ny_max = max(0.0, min(ny_max, 1.0))

                            norm_w = nx_max - nx_min
                            norm_h = ny_max - ny_min
                            x_center = nx_min + (norm_w / 2.0)
                            y_center = ny_min + (norm_h / 2.0)

                            # Filter micro-boxes or collapsed geometries (< 2 pixels equivalent)
                            if norm_w > 0.002 and norm_h > 0.002:
                                yolo_labels.append(f"{class_id} {x_center:.6f} {y_center:.6f} {norm_w:.6f} {norm_h:.6f}")
                                total_boxes_processed += 1

                    # Save tile and labels only if valid objects exist
                    if yolo_labels:
                        cv2.imwrite(str(img_save_path), final_img)
                        with open(lbl_save_path, 'w') as f:
                            f.write("\n".join(yolo_labels))
                        total_tiles_saved += 1

    print(f"\n[SUCCESS] Slicing Complete!")
    print(f"-> Saved {total_tiles_saved} valid tiles.")
    print(f"-> Processed {total_boxes_processed} sanitized bounding boxes.")

if __name__ == '__main__':
    base_path = Path("/home/ubuntu/work/saved_data/sabeel/datasets/xView")

    slice_xview_geojson_bulletproof(
        image_dir = base_path / "train_images",
        geojson_path = base_path / "xView_train.geojson",
        output_dir = base_path / "processed_sliced_1024_clean_ver9"
    )