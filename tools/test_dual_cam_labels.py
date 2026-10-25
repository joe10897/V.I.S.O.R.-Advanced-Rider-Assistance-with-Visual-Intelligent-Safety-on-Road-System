#!/usr/bin/env python3
"""
V.I.S.O.R. Dual Camera Object-Label Terminal Diagnostic & Verification Tool
Tests and outputs detailed object detection labels, bounding boxes, distances, 
and threat levels for both Front and Rear cameras.
"""
import os
import sys
import time
import argparse
import cv2
import numpy as np

# Ensure project paths
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO_DIR = os.path.join(ROOT_DIR, "YOLOv26_DEMO")
sys.path.insert(0, ROOT_DIR)
sys.path.insert(0, DEMO_DIR)

from engine_yolo26 import TaiwanTrafficEngine
from spatial_fusion import SpatialFusion

def run_camera_test(role="front", video_file=None, max_frames=8):
    print("=" * 88)
    cam_name = "CAM 0 [FRONT - 120° Sony IMX662 / FCW + LSTR]" if role == "front" else "CAM 1 [REAR - 173° Fisheye OV5647 / BSD + RCW]"
    print(f"  >>> 正在啟動 {cam_name} OBJECT-LABEL 推論測試 <<<")
    print("=" * 88)

    # 1. Initialize YOLO26n Engine
    model_path = os.path.join(ROOT_DIR, "models", "yolo26n_tw_titan.onnx")
    if not os.path.exists(model_path):
        model_path = os.path.join(ROOT_DIR, "models", "yolo26n_tw_titan.pt")
    
    engine = TaiwanTrafficEngine(model_path=model_path, imgsz=(288, 384), rect=True)
    fusion = SpatialFusion(camera=role, focal_length=260 if role == "front" else 185)

    # 2. Resolve video path
    if not video_file or not os.path.exists(video_file):
        samples_dir = os.path.join(ROOT_DIR, "sample_videos")
        if role == "front":
            candidate = os.path.join(samples_dir, "f0ace550-ad5d-424a-8c45-6999318bcd10.mp4")
        else:
            candidate = os.path.join(samples_dir, "crush_2.mp4")
        if os.path.exists(candidate):
            video_file = candidate
        else:
            files = [os.path.join(samples_dir, f) for f in os.listdir(samples_dir) if f.endswith(".mp4")]
            video_file = files[0] if files else None

    if not video_file or not os.path.exists(video_file):
        print(f"[錯誤] 找不到測試影片檔: {video_file}")
        return

    cap = cv2.VideoCapture(video_file)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    total_f = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"[*] 影片來源: {os.path.basename(video_file)} ({total_f} 幀 @ {fps:.1f} FPS)")
    print(f"[*] 輸入張量規格: 384x288 (4:3 原生矩形) | 信心度門檻: 0.15 | NMS IoU: 0.45")
    print(f"[*] 檢測目標類別標籤: 0:pedestrian, 1:scooter, 2:car, 3:bicycle, 4:truck\n")
    print("-" * 88)

    frame_idx = 0
    while cap.isOpened() and frame_idx < max_frames:
        ret, frame = cap.read()
        if not ret:
            break
        frame_idx += 1

        t0 = time.perf_counter()
        detections = engine.infer(frame, conf=0.15)
        h, w = frame.shape[:2]
        fusion_results = fusion.process(detections, {}, (h, w))
        t1 = time.perf_counter()
        latency_ms = (t1 - t0) * 1000.0
        fps_curr = 1000.0 / latency_ms if latency_ms > 0 else 0

        # Print Frame Header
        print(f"[FRAME #{frame_idx:04d}] 鏡頭: {role.upper():5s} | 延遲: {latency_ms:5.1f} ms ({fps_curr:4.1f} FPS) | 檢出目標: {len(fusion_results)} 個")

        if not fusion_results:
            print(f"   └─ [無障礙物] 背景路況淨空 (0 detections)")
        else:
            for i, obj in enumerate(fusion_results):
                cls_name = obj.get("class", "unknown").upper()
                conf = obj.get("confidence", obj.get("conf", 0.0))
                bbox = [int(v) for v in obj.get("bbox", [0, 0, 0, 0])]
                dist = obj.get("distance", 0.0)
                threat = obj.get("threat_level", "safe").upper()
                ttc = obj.get("ttc", 0.0)
                v_rel = obj.get("rel_speed", 0.0)
                
                # Format direction / blindspot for Rear vs Front
                cx = (bbox[0] + bbox[2]) / 2.0
                if role == "rear":
                    if cx < 0.32 * w:
                        zone = "左後盲區 (BSD-L)"
                    elif cx > 0.68 * w:
                        zone = "右後盲區 (BSD-R)"
                    else:
                        zone = "正後逼近 (RCW)"
                else:
                    zone = "正前方車道 (FCW)"

                ttc_str = f"{ttc:4.1f}s" if ttc and ttc > 0 else "  -- "
                v_str = f" | 速度: {v_rel:+4.1f}m/s" if role == "rear" else ""
                print(f"   ├─ [OBJ {i+1}] LABEL: {cls_name:10s} | CONF: {conf:.2f} | BBOX: [{bbox[0]:3d},{bbox[1]:3d},{bbox[2]:3d},{bbox[3]:3d}] | 距離: {dist:4.1f}m{v_str} | TTC: {ttc_str} | 方位: {zone} | 狀態: {threat}")

        print("-" * 88)

    cap.release()
    print(f"[完成] {role.upper()} 鏡頭推論測試結束，共執行 {frame_idx} 幀。\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VISOR Dual Cam Object Label CMD Test")
    parser.add_argument("--role", default="all", choices=["front", "rear", "all"], help="Camera role to test")
    parser.add_argument("--frames", type=int, default=5, help="Number of frames to test")
    args = parser.parse_args()

    if args.role in ("front", "all"):
        run_camera_test(role="front", max_frames=args.frames)
    if args.role in ("rear", "all"):
        run_camera_test(role="rear", max_frames=args.frames)
