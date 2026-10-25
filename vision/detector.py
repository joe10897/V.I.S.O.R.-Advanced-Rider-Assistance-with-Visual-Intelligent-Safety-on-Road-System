from ultralytics import YOLO
import numpy as np
from dataclasses import dataclass
import torch

@dataclass
class Detection:
    class_id: int
    class_name: str
    confidence: float
    bbox: list[int] # [x1, y1, x2, y2]

class Detector:
    # COCO Class IDs
    # 2: car, 3: motorcycle, 5: bus, 7: truck
    VEHICLE_CLASSES = [2, 3, 5, 7]

    def __init__(self, model_name="yolov8n.pt", device=None, conf_threshold=0.25):
        if device is None:
            self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        else:
            self.device = device
            
        print(f"[INFO] Initializing YOLOv8 detector on {self.device}...")
        self.model = YOLO(model_name)
        self.conf_threshold = conf_threshold
        # Warmup
        # self.model(np.zeros((640, 640, 3), dtype=np.uint8), device=self.device, verbose=False)

    def detect(self, frame, filter_vehicles=True) -> list[Detection]:
        """
        Detect objects in the frame.
        filter_vehicles: If True, only return vehicle classes.
        """
        # Optimization: Use smaller imgsz (320) for much faster inference on Pi 5
        results = self.model(frame, imgsz=320, device=self.device, verbose=False, conf=self.conf_threshold)
        detections = []
        r = results[0]
        
        if r.boxes is None:
            return detections
            
        boxes = r.boxes.xyxy.cpu().numpy()
        scores = r.boxes.conf.cpu().numpy()
        class_ids = r.boxes.cls.cpu().numpy().astype(int)
        
        for cid, conf, box in zip(class_ids, scores, boxes):
            if filter_vehicles and cid not in self.VEHICLE_CLASSES:
                continue
                
            detections.append(Detection(
                class_id=int(cid),
                class_name=self.model.names[int(cid)],
                confidence=float(conf),
                bbox=[int(b) for b in box]
            ))
            
        return detections
