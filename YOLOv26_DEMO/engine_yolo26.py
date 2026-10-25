import os
import cv2
import numpy as np
import torch
import torch.nn as nn

# Monkey-patch PyTorch Module.__delattr__ to prevent Ultralytics fuse() crash on models without 'bn'
orig_delattr = nn.Module.__delattr__
def safe_delattr(self, name):
    try:
        orig_delattr(self, name)
    except AttributeError:
        pass
nn.Module.__delattr__ = safe_delattr

try:
    import onnxruntime as ort
except ImportError:
    ort = None

from ultralytics import YOLO

class TaiwanTrafficEngine:
    """
    Taiwan Traffic Perception Engine for V.I.S.O.R.
    Supports high-speed ONNX Runtime (ARM NEON optimized for Raspberry Pi 5)
    with seamless fallback to PyTorch .pt.
    """
    TITAN_CLASSES = {0: "pedestrian", 1: "scooter", 2: "car", 3: "bicycle", 4: "truck"}

    def __init__(self, model_path=None, device="cpu", imgsz=(288, 384), rect=True):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.dirname(current_dir)
        
        if model_path is None or not os.path.exists(model_path):
            candidates = [
                os.path.join(root_dir, "models", "yolo26n_tw_titan.onnx"),
                os.path.join(current_dir, "models", "yolo26n_tw_titan.onnx"),
                os.path.join(root_dir, "models", "yolo26n_tw_titan.pt"),
                os.path.join(current_dir, "models", "yolo26n_tw_titan.pt"),
                os.path.join(root_dir, "yolo26n_tw_titan.pt"),
                os.path.join(current_dir, "yolo26n_tw_titan.pt"),
                os.path.join(current_dir, "models", "yolo26n_tw.pt"),
                os.path.join(current_dir, "yolo26n_tw.pt"),
                os.path.join(current_dir, "yolo26n.pt"),
                "models/yolo26n_tw_titan.onnx",
                "models/yolo26n_tw_titan.pt",
            ]
            for cand in candidates:
                if os.path.exists(cand):
                    model_path = os.path.abspath(cand)
                    break
            if model_path is None or not os.path.exists(model_path):
                model_path = os.path.join(current_dir, "yolo26n.pt")

        self.model_path = model_path
        self.device = device
        self.is_onnx = str(model_path).endswith(".onnx") and (ort is not None)
        
        # Parse imgsz: default (288, 384) -> height=288, width=384
        if isinstance(imgsz, (list, tuple)):
            self.input_h = int(imgsz[0])
            self.input_w = int(imgsz[1]) if len(imgsz) > 1 else int(imgsz[0])
        else:
            self.input_h = int(imgsz)
            self.input_w = int(imgsz)
        self.imgsz = (self.input_h, self.input_w)
        self.rect = rect

        if self.is_onnx:
            # Raspberry Pi 5 Cortex-A76 Quad-Core Optimization
            opts = ort.SessionOptions()
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            opts.intra_op_num_threads = 4
            opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
            
            # Explicitly force CPUExecutionProvider on Pi 5 / Edge devices
            self.session = ort.InferenceSession(model_path, sess_options=opts, providers=['CPUExecutionProvider'])
            self.inp_name = self.session.get_inputs()[0].name
            
            # Inspect actual model input dimensions if static
            inp_shape = self.session.get_inputs()[0].shape
            if len(inp_shape) == 4:
                if isinstance(inp_shape[2], int) and inp_shape[2] > 0:
                    self.input_h = inp_shape[2]
                if isinstance(inp_shape[3], int) and inp_shape[3] > 0:
                    self.input_w = inp_shape[3]
                self.imgsz = (self.input_h, self.input_w)
            
            self.class_names = dict(self.TITAN_CLASSES)
            self.taiwan_classes = list(self.class_names.keys())
            print(f"[AI Engine] [ONNX Runtime] Initialized with: {model_path}")
            print(f"             Target Hardware: Pi 5 ARM Cortex-A76 (4 threads, NEON FP32, shape={self.input_w}x{self.input_h})")
            print(f"             Classes ({len(self.taiwan_classes)}): {self.class_names}")
        else:
            try:
                torch.set_num_threads(4)
            except Exception:
                pass
            print(f"[AI Engine] [PyTorch] Loading local YOLO model from: {model_path} (imgsz={imgsz}, rect={rect})")
            self.model = YOLO(model_path)
            
            # Extract classes
            self.taiwan_classes = []
            self.class_names = {}
            target_keywords = {
                "car": "car", "automobile": "car", "vehicle": "car",
                "motorcycle": "scooter", "scooter": "scooter", "motorbike": "scooter",
                "bicycle": "bicycle", "bike": "bicycle", "bus": "truck",
                "truck": "truck", "person": "pedestrian", "pedestrian": "pedestrian"
            }
            model_names = getattr(self.model, 'names', {})
            if isinstance(model_names, dict):
                for cls_id, raw_name in model_names.items():
                    name_lower = str(raw_name).lower()
                    for kw, mapped in target_keywords.items():
                        if kw in name_lower:
                            self.taiwan_classes.append(int(cls_id))
                            self.class_names[int(cls_id)] = mapped
                            break
            if not self.taiwan_classes:
                self.class_names = dict(self.TITAN_CLASSES)
                self.taiwan_classes = list(self.class_names.keys())
            print(f"[AI Engine] Active Detection Classes ({len(self.taiwan_classes)}): {self.class_names}")

    def infer(self, frame, conf=0.15):
        if frame is None:
            return []

        if self.is_onnx:
            return self._infer_onnx(frame, conf)
        else:
            return self._infer_pytorch(frame, conf)

    def _infer_onnx(self, frame, conf=0.15):
        try:
            h, w = frame.shape[:2]
            
            # 1. Fast Resize & RGB Conversion (Zero Torch overhead)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            resized = cv2.resize(rgb, (self.input_w, self.input_h), interpolation=cv2.INTER_LINEAR)
            
            # HWC -> CHW, normalize to [0.0, 1.0]
            blob = resized.transpose(2, 0, 1).astype(np.float32) / 255.0
            blob = np.expand_dims(blob, axis=0)

            # 2. ONNX Runtime Forward Pass
            preds = self.session.run(None, {self.inp_name: blob})[0][0].T  # [2268, 9]

            # 3. Vectorized Confidence & Class Thresholding
            boxes = preds[:, :4]
            scores = preds[:, 4:]
            class_ids = np.argmax(scores, axis=1)
            confidences = np.max(scores, axis=1)

            mask = confidences >= conf
            if not np.any(mask):
                return []

            boxes = boxes[mask]
            confidences = confidences[mask]
            class_ids = class_ids[mask]

            # 4. Coordinate Rescaling back to original frame dimensions
            scale_x = w / float(self.input_w)
            scale_y = h / float(self.input_h)
            
            cx = boxes[:, 0]
            cy = boxes[:, 1]
            bw = boxes[:, 2]
            bh = boxes[:, 3]
            
            x1 = (cx - bw * 0.5) * scale_x
            y1 = (cy - bh * 0.5) * scale_y
            bw_scaled = bw * scale_x
            bh_scaled = bh * scale_y

            # 5. Native OpenCV C++ NMS
            nms_boxes = np.stack([x1, y1, bw_scaled, bh_scaled], axis=1).tolist()
            indices = cv2.dnn.NMSBoxes(nms_boxes, confidences.tolist(), conf, 0.45)

            results = []
            if len(indices) > 0:
                for idx in indices.flatten():
                    bx1 = float(max(0, x1[idx]))
                    by1 = float(max(0, y1[idx]))
                    bx2 = float(min(w, bx1 + bw_scaled[idx]))
                    by2 = float(min(h, by1 + bh_scaled[idx]))
                    cid = int(class_ids[idx])
                    
                    results.append({
                        "bbox": [round(bx1, 1), round(by1, 1), round(bx2, 1), round(by2, 1)],
                        "class": self.class_names.get(cid, "car"),
                        "conf": round(float(confidences[idx]), 2)
                    })
            return results
        except Exception:
            return []

    def _infer_pytorch(self, frame, conf=0.15):
        try:
            with torch.inference_mode():
                results = self.model.predict(
                    source=frame,
                    classes=self.taiwan_classes,
                    conf=conf,
                    imgsz=self.imgsz,
                    rect=self.rect,
                    device=self.device,
                    verbose=False
                )
            parsed_results = []
            if len(results) > 0:
                boxes = results[0].boxes
                for box in boxes:
                    cls_id = int(box.cls[0])
                    conf_val = float(box.conf[0])
                    xyxy = box.xyxy[0].cpu().numpy().tolist()
                    parsed_results.append({
                        "bbox": xyxy,
                        "class": self.class_names.get(cls_id, "car"),
                        "conf": round(conf_val, 2)
                    })
            return parsed_results
        except Exception:
            return []

if __name__ == "__main__":
    engine = TaiwanTrafficEngine()
    print("Taiwan Traffic Engine Initialized with YOLOv26n")
    print(f"Targeting: {list(engine.class_names.values())}")
