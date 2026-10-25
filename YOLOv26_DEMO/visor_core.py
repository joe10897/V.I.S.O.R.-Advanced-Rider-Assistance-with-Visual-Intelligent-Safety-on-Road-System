import cv2
import numpy as np
import time
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine_yolo26 import TaiwanTrafficEngine
from spatial_fusion import SpatialFusion
try:
    from engine_lstr import LSTR_Engine
except ImportError:
    LSTR_Engine = None
try:
    from engine_ufld import UFLDv2Engine
except ImportError:
    UFLDv2Engine = None
try:
    from engine_cv_lane import CVLaneMagnetEngine
except ImportError:
    CVLaneMagnetEngine = None

class VisorCore:
    """
    Production-ready V.I.S.O.R. pipeline wrapper for main_controller.py.
    Front camera: YOLOv26n + CV-Magnet / UFLD-v2 / LSTR + SpatialFusion v2
    Rear camera:  YOLOv26n + SpatialFusion v2 (no lane)
    """

    def __init__(self, model_path=None, imgsz=(288, 384), rect=True,
                 focal_length_front=260, focal_length_rear=185,
                 fov_front=120, fov_rear=173):
        self.detector = TaiwanTrafficEngine(model_path=model_path, imgsz=imgsz, rect=rect)
        self.focal_length_front = focal_length_front
        self.focal_length_rear = focal_length_rear
        self.fov_front = fov_front
        self.fov_rear = fov_rear
        # Dedicated spatial fusion instances with IMX662 calibrated FOV/focal lengths
        self.fusion_front = SpatialFusion(focal_length=focal_length_front, camera="front", fov=fov_front)
        self.fusion_rear = SpatialFusion(focal_length=focal_length_rear, camera="rear", fov=fov_rear)
        self.lane_engine = None  # lazy init for front camera
        self.lane_skip = 0       # CV-Magnet runs at 0.4ms (zero skip needed)
        self._lane_counter = 0
        self._cached_lanes = {}

    @property
    def fusion(self):
        """Backward compatibility for legacy references"""
        return self.fusion_rear

    def enable_lane(self, lane_model="cv_magnet", skip_frames=0):
        try:
            if lane_model == "cv_magnet" and CVLaneMagnetEngine is not None:
                self.lane_engine = CVLaneMagnetEngine(skip_frames=skip_frames)
                self.lane_skip = skip_frames
                print("[VisorCore] CV-Magnet Ground-Snapping Lane Engine enabled (0.4ms Native, zero DL overhead).")
            elif lane_model == "ufld" and UFLDv2Engine is not None:
                self.lane_engine = UFLDv2Engine(skip_frames=skip_frames or 2)
                self.lane_skip = skip_frames or 2
                print("[VisorCore] UFLD-v2 Ground-Tracking Lane Engine enabled (320x800 ONNX, polynomial fitting).")
            elif LSTR_Engine is not None:
                self.lane_engine = LSTR_Engine(variant="onnx", skip_frames=skip_frames)
                self.lane_skip = skip_frames
                print("[VisorCore] LSTR ONNX Edge Lane Engine enabled (180x320, ~1.1ms).")
            else:
                self.lane_engine = None
        except Exception as e:
            try:
                print(f"[VisorCore] Primary lane engine fallback ({e}), attempting LSTR...")
                self.lane_engine = LSTR_Engine(variant="onnx", skip_frames=skip_frames)
            except Exception as e2:
                print(f"[VisorCore] Note: Lane model unavailable ({e2}). Using spatial geometric fusion.")
                self.lane_engine = None

    def process_front(self, frame):
        """Front camera: YOLO + LSTR lane + fusion_front, returns (threats, lanes)"""
        h, w = frame.shape[:2]
        self._last_fw = w
        detections = self.detector.infer(frame)

        if self.lane_engine:
            try:
                lanes = self.lane_engine.infer(frame)
            except Exception:
                lanes = {}
        else:
            lanes = {}

        results = self.fusion_front.process(detections, lanes, (h, w))
        for r in results:
            r['camera'] = 'front'
        return results, lanes

    def process_rear(self, frame):
        """Rear camera: YOLO only + fusion_rear, no lane detection. Returns (threats, empty_lanes)"""
        h, w = frame.shape[:2]
        self._last_fw = w
        detections = self.detector.infer(frame)
        results = self.fusion_rear.process(detections, {}, (h, w))
        for r in results:
            r['camera'] = 'rear'
        return results, {}

    def detections_to_threats(self, fusion_results, camera="rear"):
        """
        Convert SpatialFusion results to the four-direction threat format
        used by main_controller's telemetry payload.
        側向盲區 (left, right) 最高為 caution (純視覺、絕不蜂鳴)；
        前方急煞 (front) 與 正後方逼車 (rear) 依逼近急迫度輸出 danger/warning。
        """
        threats = {d: None for d in ["rear", "front", "left", "right"]}

        for r in fusion_results:
            level_str = r.get("threat_level", "safe")
            if level_str not in ("critical", "warning", "caution"):
                continue

            bbox = r["bbox"]
            cx = (bbox[0] + bbox[2]) / 2
            fw = getattr(self, '_last_fw', 640)

            if camera == "rear":
                # 後鏡頭 (173° 魚眼鏡頭)：依水平位置映射至左右盲區 (BSD) 或正後方逼車 (RCW)
                if cx < 0.32 * fw:
                    direction = "left"
                elif cx > 0.68 * fw:
                    direction = "right"
                else:
                    direction = "rear"
            else:
                # 前鏡頭 (120° 廣角鏡頭)：永遠為前方 (FCW) 前向防撞或車距預警
                direction = "front"

            # 核心規範：側向盲區 (left, right) 嚴禁發出 danger/warning 聲響，最高為 caution (純視覺)
            if direction in ("left", "right") and level_str in ("critical", "warning"):
                level_str = "caution"

            threat = {
                "direction": direction,
                "level": "danger" if level_str == "critical" else ("warning" if level_str == "warning" else "caution"),
                "message": f"{self._zh_dir(direction)} {r['class']} {r['distance']:.1f}m",
                "dist": r["distance"],
                "class_name": r["class"],
                "ttc": r.get("ttc", 0),
            }

            if threats[direction] is None:
                threats[direction] = threat
            elif threat["level"] == "danger" and threats[direction]["level"] != "danger":
                threats[direction] = threat
            elif threat["level"] == "warning" and threats[direction]["level"] == "caution":
                threats[direction] = threat

        # 優先回傳緊急危險 (danger)，前方急煞與後方逼車優先於盲區
        prio_order = ["front", "rear", "left", "right"]
        for prio_dir in prio_order:
            t = threats[prio_dir]
            if t and t["level"] == "danger":
                return t
        for prio_dir in prio_order:
            t = threats[prio_dir]
            if t and t["level"] == "warning":
                return t
        for prio_dir in prio_order:
            t = threats[prio_dir]
            if t and t["level"] == "caution":
                return t
        return None

    def _zh_dir(self, direction):
        return {"rear": "後方", "front": "前方", "left": "左側", "right": "右側"}.get(direction, "")

    def build_logs(self, all_detections, threat_data):
        logs = []
        if threat_data:
            logs.append({"type": threat_data["level"], "msg": threat_data["message"]})
        for det in all_detections:
            if det.get("is_threat"):
                logs.append({
                    "type": det.get("threat_level", "warning"),
                    "msg": f"{det.get('class', '目標')} 距離 {det.get('distance', 0):.1f}m (TTC: {det.get('ttc', 0):.1f}s)"
                })
        return logs
