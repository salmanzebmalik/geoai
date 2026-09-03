from ultralytics import YOLO
import cv2
from pathlib import Path


class YOLO11Pipeline:
    def __init__(self, model_path: str = "app/models/download_models/yolo11/best_yolo11v1.pt"):
        self.model = YOLO(model_path)

    def predict(self, image_path: str, conf: float = 0.25):
        if not Path(image_path).exists():
            raise FileNotFoundError(f"Image path does not exist: {image_path}")

        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Failed to decode image from path: {image_path}")

        results = self.model(img, conf=conf)
        detections = []

        for r in results:
            for box in r.boxes:
                coords = box.xyxy[0].tolist()
                confidence = float(box.conf[0].item())
                class_id = int(box.cls[0].item())
                class_name = self.model.names[class_id]

                detections.append({
                    "bbox": coords,
                    "confidence": confidence,
                    "class_id": class_id,
                    "class_name": class_name
                })

        return detections