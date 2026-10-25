import asyncio
import json
import time
import os
import sys
import cv2
import numpy as np
import glob
import psutil
import argparse
import subprocess
import math
from concurrent.futures import ThreadPoolExecutor

import base64
import threading
from communication.udp_broadcaster import UdpBroadcaster
from communication.udp_listener import UdpListener
from communication.websocket_server import VisorWebSocketServer
from communication.bluetooth_server import VisorBluetoothServer
from vision.frame_reader import FrameReader
from vision.recorder import DashcamRecorder
from vision.sensor_sim import SensorSim
from trip_logger import TripLogger
from config_loader import load_config, save_config

# New YOLOv26 pipeline
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "YOLOv26_DEMO"))
from visor_core import VisorCore

class MainController:
    """
    V.I.S.O.R. 系統主控制器
    負責協調感測器數據輸入、AI 推理與數據分發。
    支援實車模式、展示模擬模式 (Demo) 以及展覽演示循環模式 (Exhibition)。
    """
    def __init__(self, video_source=None, demo_mode=False, exhibition_mode=False):
        self.config = load_config()
        self.demo_mode = demo_mode
        self.exhibition_mode = exhibition_mode or self.config.get('system', {}).get('exhibition_mode_default', False)
        self.exhibition_start_time = time.time()
        self.show_visual = False
        
        # Network Config
        net_conf = self.config['network']
        self.udp_broadcaster = UdpBroadcaster(ip=net_conf['broadcast_ip'], port=net_conf['udp_port'])
        self.udp_listener = UdpListener(port=net_conf['hud_listener_port'])
        self.ws_server = VisorWebSocketServer(host=net_conf['websocket_host'], port=net_conf['websocket_port'])
        self.ws_server.command_callback = self.handle_command
        
        # Bluetooth Server
        self.bt_server = VisorBluetoothServer(name="VISOR_Core")
        self.bt_server.command_callback = self.handle_command
        
        self.running = False
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.frame_count = 0
        self.ai_skip_rate = 1  # 20Hz steady Ping-Pong loop (1 camera per tick)
        self.last_ai_results = (None, None, [])

        # Asymmetric Ping-Pong AI Scheduler State
        self.ping_pong_turn = "rear"  # Start with rear defense
        self.cached_rear_results = []
        self.cached_front_results = []
        self.cached_front_lanes = {}
        self.cached_rear_threat = None
        self.cached_front_threat = None
        self.last_rear_infer_time = 0.0
        self.last_front_infer_time = 0.0
        self.rear_danger_streak = 0

        # Vision Config
        vis_conf = self.config['vision']
        cfg_source_front = vis_conf.get('source_front', None)
        cfg_source_rear = vis_conf.get('source_rear', vis_conf.get('source', 0))
        cfg_type_front = vis_conf.get('source_front_type', 'auto')
        cfg_type_rear = vis_conf.get('source_rear_type', 'auto')
        
        cfg_rotate_front = vis_conf.get('rotate_front', 0)
        cfg_rotate_rear  = vis_conf.get('rotate_rear',  0)
        
        self.video_source_front = None
        self.video_source_rear = cfg_source_rear
        
        if video_source is not None:
            self.video_source_rear = video_source
        elif self.demo_mode:
            samples = glob.glob("sample_videos/*.mp4")
            if samples:
                self.video_source_rear = samples[0]
                print(f"[DEMO] Using sample video: {self.video_source_rear}")

        # Clean any lingering camera processes before opening hardware pipelines (Linux only)
        if os.name != 'nt':
            try:
                subprocess.run("pkill -9 -f rpicam 2>/dev/null; pkill -9 -f libcamera 2>/dev/null", shell=True)
                time.sleep(0.3)
            except Exception:
                pass

        # Instantiate Readers (Non-blocking asynchronous initialization)
        self.reader_front = None
        if cfg_source_front is not None and not self.demo_mode and video_source is None:
            self.video_source_front = cfg_source_front
            print(f"[INFO] Initializing Front Camera: {self.video_source_front} (type={cfg_type_front}, rotate={cfg_rotate_front})")
            try:
                self.reader_front = FrameReader(self.video_source_front, rotate=cfg_rotate_front, camera_type=cfg_type_front, role="front")
            except Exception as e:
                print(f"[WARN] 前鏡頭啟動警告: {e}")
                self.reader_front = None

        try:
            self.reader_rear = FrameReader(self.video_source_rear, rotate=cfg_rotate_rear, camera_type=cfg_type_rear, role="rear")
        except Exception as e:
            print(f"[WARN] 後鏡頭啟動警告: {e}")
            self.reader_rear = FrameReader(self.video_source_rear, role="rear")

        print(f"[INFO] Using Rear Camera: {self.video_source_rear} (type={cfg_type_rear}, rotate={cfg_rotate_rear})")

        # 實體鏡頭防衝突驗證：若兩者皆連線且綁定至相同 /dev/video* 節點，停用後鏡頭以避免誤警
        if self.reader_front and self.reader_rear:
            if getattr(self.reader_front, 'is_hardware_connected', False) and getattr(self.reader_rear, 'is_hardware_connected', False):
                if getattr(self.reader_front, 'actual_source', None) == getattr(self.reader_rear, 'actual_source', None) and not self.demo_mode:
                    print(f"[WARN] [!] 偵測到前鏡頭與後鏡頭綁定至相同硬體節點 ({self.reader_front.actual_source})！自動停用後鏡頭，以單前鏡頭 ADAS 模式運行。")
                    self.reader_rear.is_hardware_connected = False
                    self.reader_rear.is_dummy = True
        
        # Initialize AI Models (YOLOv26n + LSTR CULane + SpatialFusion v2 with IMX662 configs)
        visor_conf = self.config.get("visor", {})
        raw_imgsz = vis_conf.get("imgsz", visor_conf.get("imgsz", [288, 384]))
        model_imgsz = tuple(raw_imgsz) if isinstance(raw_imgsz, (list, tuple)) else raw_imgsz
        model_rect = vis_conf.get("rect", visor_conf.get("rect", True))
        model_path = vis_conf.get("model_path", None)
        f_len_front = vis_conf.get("focal_length_front", vis_conf.get("focal_length", 260))
        f_len_rear = vis_conf.get("focal_length_rear", 185)
        self.fov_front = vis_conf.get("fov_front", 120)
        self.fov_rear = vis_conf.get("fov_rear", 173)
        self.visor = VisorCore(
            model_path=model_path,
            imgsz=model_imgsz,
            rect=model_rect,
            focal_length_front=f_len_front,
            focal_length_rear=f_len_rear,
            fov_front=self.fov_front,
            fov_rear=self.fov_rear
        )
        # Enable lane detection for front camera (CV-Magnet / LSTR)
        if self.video_source_front or not self.demo_mode:
            lane_m = vis_conf.get("lane_model", visor_conf.get("lane_model", "cv_magnet"))
            lane_sk = vis_conf.get("lane_skip", visor_conf.get("lane_skip", 0))
            self.visor.enable_lane(lane_model=lane_m, skip_frames=lane_sk)
        
        self.sensor_sim = SensorSim()
        
        # Initialize Recorder for Dashcam & Snapshots
        self.recorder = DashcamRecorder(fps=15.0, width=640, height=480)
        self.sentry_enabled = False
        self.last_frame_front = None
        self.last_frame_rear = None
        
        # HUD Config (load from persistent config)
        self.hud_config = self.config.get("hud_config", {
            "speed": True,
            "camera": True,
            "nav": True,
            "time": True,
            "brightness": 128,
            "mirror": True,
            "flip_v": True
        })
        
        self.hud_timeout = self.config['system']['hud_timeout']
        self.app_data = {}

        # 車載黑盒子路測記錄器與手機真實 GPS / 陀螺儀上行
        self.trip_logger = TripLogger()
        self.phone_telemetry = None
        self.phone_telemetry_last_rx = 0.0

        # 啟動即刻廣播初始待機遙測，確保 HUD 開機 0 秒立即點亮並連線
        self.udp_broadcaster.send_data({
            "timestamp": time.time(),
            "speed": 0,
            "tilt": 0,
            "warning": None,
            "radar_targets": [],
            "ai_results": [],
            "system": {
                "pi5_status": "online",
                "hud_status": "online",
                "cpu": 0,
                "mem": 0,
                "temp": 0
            },
            "recording": {
                "is_recording": False,
                "duration": 0
            },
            "hud_config": self.hud_config,
            "app_data": {},
            "alert": 0
        })

    def get_cpu_temp(self):
        """獲取 CPU 溫度 (適用於 Raspberry Pi / Linux)"""
        try:
            if os.path.exists("/sys/class/thermal/thermal_zone0/temp"):
                with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                    temp = int(f.read()) / 1000.0
                    return temp
            return 0.0 # Windows 或非 Pi 系統返回 0
        except:
            return 0.0

    def broadcast_to_clients(self, payload):
        """同步廣播至藍牙及非同步 WebSocket 用戶端"""
        self.bt_server.broadcast(payload)
        if hasattr(self, 'ws_server') and self.ws_server:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.ws_server.broadcast(payload))
            except RuntimeError:
                pass

    def handle_command(self, data):
        action = data.get("action")
        if action == "ping":
            self.bt_server.broadcast({
                "type": "pong",
                "timestamp": time.time()
            })
            return
        elif action == "set_sentry":
            self.sentry_enabled = data.get("enabled", False)
            print(f"[COMMAND] Sentry Mode: {self.sentry_enabled}")
        elif action in ["take_snapshot", "snapshot"]:
            f_front = self.last_frame_front if self.last_frame_front is not None else (self.reader_front.read() if self.reader_front else None)
            f_rear = self.last_frame_rear if self.last_frame_rear is not None else (self.reader_rear.read() if self.reader_rear else None)
            saved = self.recorder.take_snapshot(f_front, f_rear)
            print(f"[COMMAND] 📸 拍照快照已儲存: {saved}")
            self.broadcast_to_clients({
                "type": "notification",
                "level": "success",
                "title": "📸 行車快照已儲存",
                "message": f"雙鏡頭高畫質快照已保存 ({len(saved)} 張照片)"
            })
            # 延遲 0.4 秒待檔案寫入硬碟後立即推送最新相簿列表
            def _push_updated_list():
                time.sleep(0.4)
                items = self.recorder.list_snapshots()
                self.broadcast_to_clients({
                    "type": "snapshot_list",
                    "files": items
                })
            threading.Thread(target=_push_updated_list, daemon=True).start()
        elif action == "get_snapshots":
            items = self.recorder.list_snapshots()
            print(f"[COMMAND] 📸 查詢快照清單: 共 {len(items)} 張照片")
            self.broadcast_to_clients({
                "type": "snapshot_list",
                "files": items
            })
        elif action == "get_snapshot_image":
            filename = data.get("filename")
            max_width = data.get("max_width", 240)
            img_b64 = self.recorder.get_snapshot_base64(filename, max_width=max_width)
            if img_b64:
                self.broadcast_to_clients({
                    "type": "snapshot_image",
                    "filename": filename,
                    "data": img_b64
                })
        elif action == "delete_snapshot":
            filename = data.get("filename")
            self.recorder.delete_snapshot(filename)
            items = self.recorder.list_snapshots()
            self.broadcast_to_clients({
                "type": "snapshot_list",
                "files": items
            })
        elif action == "toggle_recording":
            is_rec = self.recorder.toggle_recording(data.get("enabled"))
            msg = "🔴 已啟動行車錄影" if is_rec else "⏹️ 行車錄影已停止並存檔"
            self.bt_server.broadcast({
                "type": "notification",
                "level": "info",
                "title": "行車記錄儀",
                "message": msg
            })
        elif action == "set_hud_config":
            new_conf = data.get("config", {})
            self.hud_config.update(new_conf)
            # 保存到文件以持久化
            self.config["hud_config"] = self.hud_config
            save_config(self.config)
            print(f"[COMMAND] HUD Config Updated & Saved: {self.hud_config}")
            # 即刻廣播至 Pi Zero HUD 確保亮度/翻轉/型號立即生效
            self.udp_broadcaster.send_data({
                "timestamp": time.time(),
                "hud_config": self.hud_config
            })
        elif action == "set_exhibition":
            self.exhibition_mode = bool(data.get("enabled", True))
            if self.exhibition_mode:
                self.exhibition_start_time = time.time()
            print(f"[COMMAND] 展覽演示模式 (Exhibition Mode): {self.exhibition_mode}")
            resp = {
                "type": "exhibition_status",
                "enabled": self.exhibition_mode
            }
            self.bt_server.broadcast(resp)
            if hasattr(self, 'ws_server') and self.ws_server:
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self.ws_server.broadcast(resp))
                except RuntimeError:
                    pass
            self.bt_server.broadcast({
                "type": "notification",
                "level": "info",
                "title": "展覽演示模式",
                "message": f"展覽全情境演示已{'啟動' if self.exhibition_mode else '關閉'}"
            })
        elif action == "app_sync":
            self.app_data = data
        elif action == "system_power":
            target = data.get("target")
            if target == "pi5":
                print("[COMMAND] 電源管理：主機 Pi 5 正準備關機...")
                self.bt_server.broadcast({
                    "type": "notification",
                    "level": "warning",
                    "title": "系統電源管理",
                    "message": "主機 Pi 5 正在安全關機..."
                })
                def _do_pi5_shutdown():
                    time.sleep(1.0)
                    try:
                        os.system("sync")
                    except Exception:
                        pass
                    cmds = [
                        "sudo /bin/systemctl poweroff",
                        "sudo /sbin/poweroff",
                        "sudo /sbin/shutdown -h now",
                        "sudo shutdown -h now",
                        "systemctl poweroff"
                    ]
                    for cmd in cmds:
                        try:
                            ret = subprocess.run(cmd, shell=True, timeout=3)
                            if ret.returncode == 0:
                                break
                        except Exception:
                            pass
                threading.Thread(target=_do_pi5_shutdown, daemon=True).start()
            elif target == "pizero":
                print("[COMMAND] 電源管理：正在向 Pi Zero HUD 發送關機指令...")
                if hasattr(self, 'udp_broadcaster') and self.udp_broadcaster:
                    self.udp_broadcaster.send_immediate({"system_command": "shutdown"}, count=8)
                self.bt_server.broadcast({
                    "type": "notification",
                    "level": "warning",
                    "title": "系統電源管理",
                    "message": "已向 Pi Zero HUD 發送關機指令"
                })
        elif action == "telemetry_sync":
            # 接收手機端回傳之真實 GPS 速度、傾角與經緯度 (Uplink)
            telemetry = data.get("telemetry", {})
            self.phone_telemetry = telemetry
            self.phone_telemetry_last_rx = time.time()

            # 鎖定手機端觀測到的最高時速 (避免 4Hz 取樣因瞬時掉速或延遲丟失峰值速度)
            t_max_speed = float(telemetry.get("max_speed", 0.0) or 0.0)
            if t_max_speed > self.trip_logger.max_speed:
                self.trip_logger.max_speed = t_max_speed

            # 時間智慧同步：若手機帶有 GPS epoch 時間且與 Pi 5 時間偏差 > 60 秒，自動校時
            client_epoch = telemetry.get("epoch")
            if client_epoch and os.name != 'nt':
                try:
                    c_epoch = float(client_epoch)
                    if abs(time.time() - c_epoch) > 60:
                        subprocess.run(f"sudo date -s @{int(c_epoch)}", shell=True, timeout=1.0)
                        print(f"[TIME_SYNC] 成功由手機 GPS 同步 Pi 5 系統時間: epoch={c_epoch}")
                except Exception:
                    pass
        elif action == "start_trip_log":
            label = data.get("label", "RoadTest")
            trip_id = data.get("trip_id")
            timestamp_str = data.get("timestamp_str")
            client_epoch = data.get("epoch")
            if client_epoch and os.name != 'nt':
                try:
                    c_epoch = float(client_epoch)
                    subprocess.run(f"sudo date -s @{int(c_epoch)}", shell=True, timeout=1.0)
                    print(f"[TIME_SYNC] 啟動路測時已強制同步 Pi 5 系統時間至真實手機時間戳")
                except Exception:
                    pass
            res = self.trip_logger.start_trip(label, trip_id=trip_id, timestamp_str=timestamp_str)
            self.bt_server.broadcast({
                "type": "trip_status",
                "status": res
            })
            self.bt_server.broadcast({
                "type": "notification",
                "level": "info",
                "title": "📊 路測記錄已啟動",
                "message": f"正在記錄行車軌跡與預警數據至 {res.get('trip_id', '')}.csv"
            })
        elif action == "stop_trip_log":
            summary = self.trip_logger.stop_trip()
            self.bt_server.broadcast({
                "type": "trip_summary",
                "summary": summary
            })
            if hasattr(self, 'ws_server') and self.ws_server:
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self.ws_server.broadcast({
                        "type": "trip_summary",
                        "summary": summary
                    }))
                except RuntimeError:
                    pass
            self.bt_server.broadcast({
                "type": "notification",
                "level": "success",
                "title": "✅ 路測記錄完成",
                "message": f"時長 {summary.get('duration_str', '')}，共記錄 {summary.get('records_count', 0)} 幀，累計感知 {summary.get('total_detections', 0)} 筆車種樣本"
            })
        elif action == "get_trip_logs":
            trips = self.trip_logger.list_trips()
            self.bt_server.broadcast({
                "type": "trip_logs_list",
                "trips": trips
            })
        elif action == "get_calibration_frame":
            # 車載安裝校正專用畫面：繪製水平輔助線、十字準星、AI 檢測框，壓成 240x180 透過藍牙回傳
            cam_idx = data.get("camera") or data.get("cam") or "front"
            req_w = int(data.get("width", 240))
            req_h = int(data.get("height", 180))
            req_q = int(data.get("quality", 50))

            frame = None
            is_fallback_view = False
            is_offline = False

            rear_is_dummy = getattr(self.reader_rear, 'is_dummy', False) if self.reader_rear else True
            front_is_dummy = getattr(self.reader_front, 'is_dummy', False) if self.reader_front else True

            if cam_idx == "front":
                if not front_is_dummy and self.last_frame_front is not None:
                    frame = self.last_frame_front
                elif not rear_is_dummy and self.last_frame_rear is not None:
                    frame = self.last_frame_rear
                    is_fallback_view = True
                else:
                    is_offline = True
            else: # rear
                if not rear_is_dummy and self.last_frame_rear is not None:
                    frame = self.last_frame_rear
                elif not front_is_dummy and self.last_frame_front is not None:
                    # 智慧單鏡頭備援：後鏡頭未連接 (如 OV5647 尚未載入驅動)，自動以在線之前鏡頭作為備援預覽
                    frame = self.last_frame_front
                    is_fallback_view = True
                else:
                    is_offline = True

            if is_offline:
                # 繪製深色高科技儀表風格的待機診斷圖卡，帶動態時間心跳以驗證藍牙通道運作中
                calib = np.zeros((480, 640, 3), dtype=np.uint8)
                for gx in range(0, 640, 40):
                    cv2.line(calib, (gx, 0), (gx, 480), (25, 35, 45), 1)
                for gy in range(0, 480, 40):
                    cv2.line(calib, (0, gy), (640, gy), (25, 35, 45), 1)

                cam_name = "FRONT CAM (IMX662 120°)" if cam_idx == "front" else "REAR CAM (IMX662 173°)"
                now_str = time.strftime("%H:%M:%S")

                cv2.rectangle(calib, (50, 150), (590, 330), (15, 22, 32), -1)
                cv2.rectangle(calib, (50, 150), (590, 330), (0, 165, 255), 2)

                cv2.putText(calib, f"[ {cam_name} STANDBY ]", (75, 205),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 220, 255), 2)
                cv2.putText(calib, "Check USB Port / V4L2 Device Node", (75, 250),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
                cv2.putText(calib, f"BT RFCOMM LINK OK | Sync: {now_str}", (75, 295),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 120), 1)
            else:
                calib = frame.copy()
                if is_fallback_view:
                    alt_name = "REAR (173°)" if cam_idx == "front" else "FRONT (120°)"
                    cv2.rectangle(calib, (10, 10), (410, 45), (0, 0, 0), -1)
                    cv2.putText(calib, f"[ {alt_name} SINGLE CAM PREVIEW (USB STANDBY) ]", (15, 32),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 200, 255), 2)

            ch, cw = calib.shape[:2]

            # 繪製水平校準基準線 (綠色中線) 與車身中央對齊線
            cv2.line(calib, (0, ch // 2), (cw, ch // 2), (0, 255, 0), 2)
            cv2.line(calib, (cw // 2, 0), (cw // 2, ch), (0, 255, 0), 1)
            cv2.circle(calib, (cw // 2, ch // 2), 22, (0, 255, 255), 2)
            cv2.putText(calib, "HORIZON LEVEL", (10, max(20, ch // 2 - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            # 疊加目前 AI 視覺檢測框與標籤 (僅在非離線圖卡時)
            dets = []
            if not is_offline and self.last_ai_results:
                dets = self.last_ai_results[2] or []
                for d in dets:
                    bbox = d.get("bbox", [0, 0, 0, 0])
                    x1, y1, x2, y2 = [int(b) for b in bbox]
                    c_name = d.get("class", "target").upper()
                    c_dist = d.get("distance", 0.0)
                    cv2.rectangle(calib, (x1, y1), (x2, y2), (0, 255, 255), 2)
                    cv2.putText(calib, f"{c_name} {c_dist:.1f}m", (x1, max(18, y1 - 6)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)

            # 壓縮至指定寬高 JPEG (品質 40，大小約 2.5~3KB，確保藍牙 SPP 流暢傳輸)
            thumb = cv2.resize(calib, (req_w, req_h), interpolation=cv2.INTER_AREA)
            _, enc = cv2.imencode(".jpg", thumb, [cv2.IMWRITE_JPEG_QUALITY, 40])
            b64_str = "data:image/jpeg;base64," + base64.b64encode(enc).decode("utf-8")

            calib_payload = {
                "type": "calibration_frame",
                "cam": cam_idx,
                "camera": cam_idx,
                "data": b64_str,
                "detected_count": len(dets),
                "ai_count": len(dets),
                "latency_ms": 32,
                "timestamp": time.time(),
                "online": not is_offline,
                "fallback": is_fallback_view
            }
            self.bt_server.broadcast(calib_payload)
            if hasattr(self, 'ws_server') and self.ws_server:
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self.ws_server.broadcast(calib_payload))
                except RuntimeError:
                    pass
        elif action == "test_hud_pulse":
            # 向安全帽 HUD 發送動態測試訊號 (時速 88 -> 左右盲點 -> 致命反白)，供安裝微調視角
            def _pulse_worker():
                test_seq = [
                    (88, 0, None),
                    (65, -15, {"direction": "left", "level": "warning", "dist": 8.2, "class_name": "CAR"}),
                    (65, 18, {"direction": "right", "level": "warning", "dist": 6.5, "class_name": "SCOOTER"}),
                    (30, 0, {"direction": "rear", "level": "danger", "dist": 2.8, "class_name": "CAR"})
                ]
                for spd, tilt, warn in test_seq:
                    p = {
                        "timestamp": time.time(),
                        "speed": spd,
                        "tilt": tilt,
                        "speed_source": "test",
                        "warning": warn,
                        "radar_targets": [],
                        "ai_results": [],
                        "pi5_log": [],
                        "system": {"pi5_status": "online", "hud_status": "online", "cpu": 15, "mem": 30, "temp": 42},
                        "recording": {"is_recording": False, "duration": 0},
                        "trip": self.trip_logger.get_status(),
                        "hud_config": self.hud_config,
                        "app_data": {},
                        "alert": 1 if warn and warn.get("level") == "danger" else 0
                    }
                    self.udp_broadcaster.send_data(p)
                    time.sleep(1.2)
            threading.Thread(target=_pulse_worker, daemon=True).start()
            self.bt_server.broadcast({
                "type": "notification",
                "level": "success",
                "title": "HUD 測試",
                "message": "已向安全帽 HUD 發送 5 秒全情境測試燈號"
            })

    def _generate_exhibition_telemetry(self, now):
        """
        32 秒全情境展示循環 (Acceleration, Left BSD, High-G Lean, Right BSD Danger Invert, Speed Camera, FCW)
        HUD 與手機端 100% 毫秒精準同步
        """
        elapsed = (now - self.exhibition_start_time) % 32.0
        
        # 預設狀態
        speed = 0.0
        tilt = 0.0
        warning = None
        cam_alert = None
        radar_targets = []
        detections = []
        lanes = {"left": True, "right": True}
        
        if elapsed < 6.0:
            # Phase 1: 0 - 6s 市區起步與直線加速 (0 -> 56 km/h)
            progress = elapsed / 6.0
            speed = round(progress * 56.0, 1)
            tilt = 0.0
            radar_targets = [{
                "id": 1,
                "type": "car",
                "label": "CAR (24.0m)",
                "angle": 0,
                "dist": 24.0,
                "relSpeed": 0.0,
                "ttc": None,
                "threat": "safe"
            }]
            detections = [{"class": "car", "distance": 24.0, "threat_level": "safe", "camera": "front"}]

        elif elapsed < 12.0:
            # Phase 2: 6 - 12s 巡航與左側車道盲點警示 (65 km/h, tilt -3°)
            sub_t = elapsed - 6.0
            speed = 65.0
            tilt = -3.0
            dist = round(max(4.6, 9.2 - sub_t * 0.8), 1)
            lvl = "danger" if dist <= 5.2 else "warning"
            warning = {
                "direction": "left",
                "level": lvl,
                "dist": dist,
                "class_name": "CAR",
                "message": f"左側盲點車輛逼近 ({dist}m)"
            }
            radar_targets = [
                {
                    "id": 1,
                    "type": "car",
                    "label": f"CAR ({dist}m)",
                    "angle": 235,
                    "dist": dist,
                    "relSpeed": 8.5,
                    "ttc": round(dist / 2.3, 1),
                    "threat": "critical" if lvl == "danger" else "warning"
                },
                {
                    "id": 2,
                    "type": "truck",
                    "label": "TRUCK (18.5m)",
                    "angle": 355,
                    "dist": 18.5,
                    "relSpeed": -2.0,
                    "ttc": None,
                    "threat": "safe"
                }
            ]
            detections = [
                {"class": "car", "distance": dist, "threat_level": lvl, "camera": "rear"},
                {"class": "truck", "distance": 18.5, "threat_level": "safe", "camera": "front"}
            ]

        elif elapsed < 18.0:
            # Phase 3: 12 - 18s 山道高速深傾角壓彎 (75 -> 68 km/h, 傾角高達 +25°)
            sub_t = elapsed - 12.0
            speed = round(74.0 - math.sin(sub_t / 6.0 * math.pi) * 6.0, 1)
            tilt = round(math.sin(sub_t / 6.0 * math.pi) * 25.0, 1)
            warning = None
            radar_targets = [{
                "id": 3,
                "type": "motorcycle",
                "label": "MOTO (15.2m)",
                "angle": 15,
                "dist": 15.2,
                "relSpeed": 0.5,
                "ttc": None,
                "threat": "safe"
            }]
            detections = [{"class": "motorcycle", "distance": 15.2, "threat_level": "safe", "camera": "front"}]

        elif elapsed < 24.0:
            # Phase 4: 18 - 24s 右側機車急逼與極限反白警報 (48 -> 38 km/h, 一級致命危險)
            sub_t = elapsed - 18.0
            dist = round(max(2.1, 5.2 - sub_t * 0.7), 1)
            speed = round(max(36.0, 52.0 - sub_t * 3.0), 1)
            tilt = 5.0
            warning = {
                "direction": "right",
                "level": "danger",
                "dist": dist,
                "class_name": "SCOOTER",
                "message": f"右側機車超車危險 ({dist}m)！"
            }
            radar_targets = [{
                "id": 4,
                "type": "scooter",
                "label": f"SCOOTER ({dist}m)",
                "angle": 125,
                "dist": dist,
                "relSpeed": 14.2,
                "ttc": 1.2,
                "threat": "critical"
            }]
            detections = [{"class": "scooter", "distance": dist, "threat_level": "danger", "camera": "rear"}]

        elif elapsed < 28.0:
            # Phase 5: 24 - 28s 固定測速照相提醒 (48 km/h, 限速 50km/h, 距離遞減)
            sub_t = elapsed - 24.0
            speed = round(52.0 - sub_t * 1.5, 1)
            tilt = 0.0
            cam_dist = max(20, int(115 - sub_t * 22))
            cam_alert = {"limit": 50, "distance": cam_dist}
            warning = None
            radar_targets = []
            detections = []

        else:
            # Phase 6: 28 - 32s 前方貨車急煞碰撞預警 FCW (46 -> 25 km/h)
            sub_t = elapsed - 28.0
            dist = round(max(4.2, 11.0 - sub_t * 1.8), 1)
            speed = round(max(24.0, 46.0 - sub_t * 5.2), 1)
            tilt = 0.0
            lvl = "danger" if dist < 6.5 else "warning"
            warning = {
                "direction": "front",
                "level": lvl,
                "dist": dist,
                "class_name": "TRUCK",
                "message": f"前方大貨車煞車減速 ({dist}m)"
            }
            radar_targets = [{
                "id": 5,
                "type": "truck",
                "label": f"TRUCK ({dist}m)",
                "angle": 0,
                "dist": dist,
                "relSpeed": -18.0,
                "ttc": round(dist / 4.5, 1),
                "threat": "critical" if lvl == "danger" else "warning"
            }]
            detections = [{"class": "truck", "distance": dist, "threat_level": lvl, "camera": "front"}]

        return speed, tilt, warning, radar_targets, detections, cam_alert, lanes

    async def vision_loop(self):
        """
        Asymmetric Ping-Pong AI Pipeline for Pi 5 Edge Computing:
        - Alternates between Rear (RCW/BSD defense) and Front (FCW/LSTR lane perception).
        - Prevents PyTorch OpenMP thread oversubscription on Pi 5's 4 CPU cores.
        - Rear threat preemption: When rear danger is detected, gives rear 2:1 priority.
        - Graceful single-camera fallback when only one camera is active.
        """
        loop = asyncio.get_running_loop()
        now = time.time()
        
        frame_rear = self.reader_rear.read() if self.reader_rear else None
        frame_front = self.reader_front.read() if self.reader_front else None
        
        if frame_rear is not None:
            self.last_frame_rear = frame_rear
        if frame_front is not None:
            self.last_frame_front = frame_front

        if frame_rear is None and frame_front is None:
            if self.demo_mode:
                print("[INFO] Re-looping demo video...")
                if self.reader_rear:
                    self.reader_rear.stop()
                    self.reader_rear = FrameReader(self.video_source_rear)
                    self.reader_rear.start()
                    frame_rear = self.reader_rear.read()
                if frame_rear is None: return None, None, []
            else:
                return None, None, []

        rear_active = frame_rear is not None and not getattr(self.reader_rear, 'is_dummy', False)
        front_active = frame_front is not None and not getattr(self.reader_front, 'is_dummy', False)
        
        # Primary frame for dashcam recording (prioritize rear, fallback to front)
        primary_frame = frame_rear if frame_rear is not None else frame_front

        # Initialize Recorder if needed
        if self.recorder and not hasattr(self, '_recorder_init') and primary_frame is not None:
            h, w = primary_frame.shape[:2]
            self.recorder.width = w
            self.recorder.height = h
            self._recorder_init = True

        if primary_frame is not None:
            self.recorder.add_frame(primary_frame)

        # Determine which camera to run on this tick (Ping-Pong Scheduler)
        run_camera = None
        if rear_active and front_active:
            # Check rear preemption: if rear has active danger, prioritize rear 2:1
            rear_is_danger = bool(self.cached_rear_threat and self.cached_rear_threat.get("level") == "danger")
            if rear_is_danger:
                self.rear_danger_streak += 1
                if self.rear_danger_streak % 3 != 0:
                    run_camera = "rear"
                else:
                    run_camera = "front"
            else:
                self.rear_danger_streak = 0
                run_camera = self.ping_pong_turn
                # Alternate for next tick
                self.ping_pong_turn = "front" if self.ping_pong_turn == "rear" else "rear"
        elif rear_active:
            run_camera = "rear"
        elif front_active:
            run_camera = "front"
        else:
            # Fallback for demo mode with simulated single frame
            if frame_rear is not None:
                run_camera = "rear"
            elif frame_front is not None:
                run_camera = "front"

        # Execute single camera inference (1 model uses 4 CPU cores cleanly)
        if run_camera == "rear" and frame_rear is not None:
            res = await loop.run_in_executor(self.executor, self.visor.process_rear, frame_rear)
            if isinstance(res, (tuple, list)) and len(res) == 2:
                rear_results, _ = res
            elif isinstance(res, list):
                rear_results = res
            else:
                rear_results = []
            self.cached_rear_results = rear_results
            self.cached_rear_threat = self.visor.detections_to_threats(rear_results, camera="rear") if rear_results else None
            self.last_rear_infer_time = now

        elif run_camera == "front" and frame_front is not None:
            res = await loop.run_in_executor(self.executor, self.visor.process_front, frame_front)
            if isinstance(res, (tuple, list)) and len(res) == 2:
                front_results, front_lanes = res
            elif isinstance(res, list):
                front_results, front_lanes = res, {}
            else:
                front_results, front_lanes = [], {}
            self.cached_front_results = front_results
            self.cached_front_lanes = front_lanes
            self.cached_front_threat = self.visor.detections_to_threats(front_results, camera="front") if front_results else None
            self.last_front_infer_time = now

        # Age out old detections if a camera has had no frame for > 0.8s or is not active hardware
        if (now - self.last_rear_infer_time > 0.8) or not rear_active:
            self.cached_rear_results = []
            self.cached_rear_threat = None
        if (now - self.last_front_infer_time > 0.8) or not front_active:
            self.cached_front_results = []
            self.cached_front_threat = None
            self.cached_front_lanes = {}

        # Combine threats from both cameras (priority: danger > warning > caution, front/rear > side)
        threat_data = None
        for t in [self.cached_front_threat, self.cached_rear_threat]:
            if t is None: continue
            if threat_data is None: threat_data = t; continue
            if t["level"] == "danger" and threat_data["level"] != "danger":
                threat_data = t
            elif t["level"] == "warning" and threat_data["level"] == "caution":
                threat_data = t
            elif t["direction"] in ("front", "rear") and threat_data["direction"] in ("left", "right"):
                threat_data = t

        # Combine all detections for unified 360 radar & telemetry
        all_results = list(self.cached_rear_results) + list(self.cached_front_results)

        return threat_data, primary_frame, all_results

    async def main_loop(self):
        """
        系統主迴圈。
        """
        self.running = True
        print("V.I.S.O.R. Main Controller Started.")
        
        self.reader_rear.start()
        if self.reader_front:
            self.reader_front.start()
        self.udp_listener.start()
        self.bt_server.start()
        
        # Performance Tuning: 20Hz steady Ping-Pong cadence
        self.frame_count = 0
        self.ai_skip_rate = 1 # Run 1 camera per tick for steady 20Hz cadence
        self.last_ai_results = (None, None, []) # Cache for skipped frames

        # 啟動 WebSocket Server
        async with self.ws_server.start() as server:
            print(f"WebSocket Server listening on {self.config['network']['websocket_host']}:{self.config['network']['websocket_port']}")
            
            last_time = time.time()
            try:
                last_tilt = 0
                while self.running:
                    dt = time.time() - last_time
                    last_time = time.time()
                    self.frame_count += 1

                    now = time.time()
                    cam_alert_override = None

                    # 1. Update Ego-Vehicle Sensors
                    if self.exhibition_mode:
                        exp_spd, exp_tilt, exp_warn, exp_radar, exp_dets, exp_cam, exp_lanes = self._generate_exhibition_telemetry(now)
                        active_speed = exp_spd
                        active_tilt = exp_tilt
                        speed_source = "exhibition"
                        warning = exp_warn
                        radar_targets = exp_radar
                        detections = exp_dets
                        cam_alert_override = exp_cam
                    elif self.demo_mode:
                        sensor_data = self.sensor_sim.step(dt if dt > 0 else 0.1)
                        active_speed = sensor_data['speed_kmh']
                        active_tilt = sensor_data['tilt_deg']
                        speed_source = "sim"
                    elif self.phone_telemetry and (time.time() - self.phone_telemetry_last_rx < 4.5):
                        active_speed = float(self.phone_telemetry.get("speed", 0.0) or 0.0)
                        active_tilt = float(self.phone_telemetry.get("tilt", 0.0) or 0.0)
                        speed_source = "gps"
                    else:
                        # 實車實體模式：未取得真實手機 GPS 或陀螺儀時靜止顯示 0，絕不顯示模擬假數據
                        active_speed = 0.0
                        active_tilt = 0.0
                        speed_source = "real"
                    
                    # Sentry Trigger
                    if self.sentry_enabled and not self.exhibition_mode:
                        tilt_diff = abs(active_tilt - last_tilt)
                        if tilt_diff > 10.0:
                            filename = self.recorder.trigger_event()
                            if filename:
                                await self.ws_server.broadcast({
                                    "type": "notification",
                                    "title": "哨兵模式警報",
                                    "message": f"偵測到異常震動！影像已存檔：{os.path.basename(filename)}",
                                    "level": "danger"
                                })
                    last_tilt = active_tilt

                    # Check HUD Heartbeat
                    last_hb, _, hud_ip = self.udp_listener.get_last_heartbeat()
                    if hud_ip and hud_ip != '0.0.0.0' and getattr(self.udp_broadcaster, 'broadcast_ip', '') != hud_ip:
                        self.udp_broadcaster.set_target_ip(hud_ip)
                        
                    hud_online = (time.time() - last_hb) < self.hud_timeout
                    
                    # AI 視覺或展示循環
                    if not self.exhibition_mode:
                        if self.frame_count % self.ai_skip_rate == 0:
                            warning, frame, detections = await self.vision_loop()
                            self.last_ai_results = (warning, frame, detections)
                            if detections and self.frame_count % 10 == 0:
                                summary = [f"{d.get('class','car')}({d.get('camera','?')}:{d.get('distance',0):.1f}m)" for d in detections]
                                print(f"[AI 視覺追蹤] 🎯 鎖定目標: {', '.join(summary)}")
                        else:
                            warning, _, detections = self.last_ai_results
                            frame = self.reader_rear.read()
                            if frame is not None:
                                self.recorder.add_frame(frame)
                    else:
                        # 展覽模式下，持續讀取相機畫面供快照與錄影，但目標由展覽情境驅動
                        frame = self.reader_rear.read()
                        if frame is not None:
                            self.recorder.add_frame(frame)

                    if frame is None and not self.exhibition_mode:
                        # 相機暫時無幀時，仍持續發送 HUD 與藍牙保持心跳，防止斷線
                        payload = {
                            "timestamp": time.time(),
                            "speed": round(active_speed, 1),
                            "tilt": round(active_tilt, 1),
                            "speed_source": speed_source,
                            "exhibition": False,
                            "warning": None,
                            "radar_targets": [],
                            "ai_results": [],
                            "pi5_log": [],
                            "system": {
                                "pi5_status": "demo" if self.demo_mode else "online",
                                "hud_status": "online" if hud_online else "offline",
                                "cpu": psutil.cpu_percent(),
                                "mem": psutil.virtual_memory().percent,
                                "temp": self.get_cpu_temp()
                            },
                            "recording": {
                                "is_recording": self.recorder.is_recording,
                                "duration": round(time.time() - self.recorder.rec_start_time) if self.recorder.is_recording and self.recorder.rec_start_time else 0
                            },
                            "trip": self.trip_logger.get_status(),
                            "hud_config": self.hud_config,
                            "app_data": getattr(self, 'app_data', {}),
                            "alert": 0
                        }
                        self.udp_broadcaster.send_data(payload)
                        # 藍牙通道專用精簡遙測（排除車道線、日誌陣列，確保 RFCOMM 頻寬健康）
                        bt_payload = {
                            "timestamp": payload["timestamp"],
                            "speed": payload["speed"],
                            "tilt": payload["tilt"],
                            "speed_source": payload["speed_source"],
                            "exhibition": payload["exhibition"],
                            "warning": payload["warning"],
                            "radar_targets": payload["radar_targets"],
                            "system": payload["system"],
                            "recording": payload["recording"],
                            "trip": payload["trip"],
                            "hud_config": payload["hud_config"],
                            "app_data": payload["app_data"],
                            "alert": payload["alert"]
                        }
                        self.bt_server.broadcast(bt_payload)
                        await self.ws_server.broadcast(payload)
                        await asyncio.sleep(0.05)
                        continue
                
                    # 低速與停等紅燈抑制 (Low-Speed FCW Suppression):
                    # 當車速極低或靜止 (< 3.0 km/h) 且為前向警報時，降級為 caution 提示，避免停等紅燈時被前車干擾
                    if active_speed < 3.0 and speed_source == "gps" and warning and warning.get("direction") == "front":
                        warning = dict(warning)
                        warning["level"] = "caution"

                    # 3. Construct Payload
                    pi5_logs = self.visor.build_logs(detections, warning) if (detections and not self.exhibition_mode) else []
                    if not pi5_logs and warning:
                        pi5_logs.append({"type": warning.get("level", "warning"), "msg": warning.get("message", "")})

                    # Build real-time 360 Radar targets from AI vision (實車模式)
                    if not self.exhibition_mode:
                        radar_targets = []
                        frame_w = frame.shape[1] if frame is not None else 640
                        for idx, d in enumerate(detections or []):
                            cam = d.get('camera', 'rear')
                            bbox = d.get('bbox', [0, 0, 0, 0])
                            cx_ratio = (bbox[0] + bbox[2]) / (2.0 * max(1, frame_w))
                            
                            if cam == 'front':
                                angle = round((cx_ratio - 0.5) * getattr(self, 'fov_front', 120))
                                if angle < 0: angle += 360
                            else:
                                angle = round(180 - (cx_ratio - 0.5) * getattr(self, 'fov_rear', 173))
                            
                            threat_map = {
                                "critical": "critical",
                                "warning": "critical",
                                "caution": "caution",
                                "safe": "safe"
                            }
                            
                            radar_targets.append({
                                "id": idx + 1,
                                "type": d.get("class", "car"),
                                "label": f"{d.get('class', 'car')} ({d.get('distance', 0):.1f}m)",
                                "angle": angle,
                                "dist": round(d.get("distance", 10), 1),
                                "relSpeed": round(d.get("rel_speed", 0), 1),
                                "ttc": round(d.get("ttc", 99), 1) if d.get("ttc") is not None and d.get("ttc") < 50 else None,
                                "threat": threat_map.get(d.get("threat_level", "safe"), "safe")
                            })

                    merged_app_data = dict(getattr(self, 'app_data', {}))
                    merged_app_data["speed"] = round(active_speed, 1)
                    merged_app_data["tilt"] = round(active_tilt, 1)
                    if cam_alert_override:
                        merged_app_data["cameraAlert"] = cam_alert_override

                    payload = {
                        "timestamp": time.time(),
                        "speed": round(active_speed, 1),
                        "tilt": round(active_tilt, 1),
                        "speed_source": speed_source,
                        "exhibition": self.exhibition_mode,
                        "warning": warning,
                        "radar_targets": radar_targets,
                        "ai_results": ([r.get("class", "?") for r in detections] if detections else []),
                        "pi5_log": pi5_logs,
                        "lanes": getattr(self, "cached_front_lanes", {}),
                        "system": {
                            "pi5_status": "exhibition" if self.exhibition_mode else ("demo" if self.demo_mode else "online"),
                            "hud_status": "online" if hud_online else "offline",
                            "cpu": psutil.cpu_percent(),
                            "mem": psutil.virtual_memory().percent,
                            "temp": self.get_cpu_temp()
                        },
                        "recording": {
                            "is_recording": self.recorder.is_recording,
                            "duration": round(time.time() - self.recorder.rec_start_time) if self.recorder.is_recording and self.recorder.rec_start_time else 0
                        },
                        "trip": self.trip_logger.get_status(),
                        "hud_config": self.hud_config,
                        "app_data": merged_app_data,
                        "alert": 1 if warning and warning.get("level") == "danger" and warning.get("direction") in ("front", "rear") else 0
                    }

                    # 紀錄實車路測數據 (若已啟動路測且非展覽模式)
                    if self.trip_logger.is_logging and not self.exhibition_mode:
                        curr_fps = round(1.0 / max(0.001, dt), 1) if dt > 0 else 20.0
                        self.trip_logger.log_step({
                            "speed": active_speed,
                            "tilt": active_tilt,
                            "warning": warning,
                            "lat": self.phone_telemetry.get("lat", 0.0) if self.phone_telemetry else 0.0,
                            "lng": self.phone_telemetry.get("lng", 0.0) if self.phone_telemetry else 0.0,
                            "heading": self.phone_telemetry.get("heading", 0.0) if self.phone_telemetry else 0.0,
                            "detections": detections or [],
                            "detections_count": len(detections) if detections else 0,
                            "fps": curr_fps,
                            "cpu": payload["system"]["cpu"],
                            "temp": payload["system"]["temp"],
                            "speed_source": speed_source
                        })
                    
                    # 4. Broadcast
                    # 專為 Pi Zero 1.3" OLED HUD 打造的極致輕量化 UDP 封包 (<250 bytes，100% 避免 Wi-Fi MTU 分片丟包與卡頓)
                    hud_payload = {
                        "timestamp": now,
                        "speed": round(active_speed, 1),
                        "tilt": round(active_tilt, 1),
                        "speed_source": speed_source,
                        "warning": warning,
                        "alert": 1 if warning and warning.get("level") == "danger" else 0,
                        "app_data": {
                            "speed": round(active_speed, 1),
                            "tilt": round(active_tilt, 1),
                            "cameraAlert": cam_alert_override or merged_app_data.get("cameraAlert")
                        },
                        "hud_config": self.hud_config,
                        "system": {
                            "pi5_status": "online",
                            "hud_status": "online" if hud_online else "offline",
                            "cpu": payload["system"]["cpu"],
                            "temp": payload["system"]["temp"]
                        }
                    }
                    self.udp_broadcaster.send_data(hud_payload)
                    await self.ws_server.broadcast(payload)
                    # 藍牙 SPP 專屬輕量遙測（去除數 KB 的車道線多項式與冗餘 AI 標籤，極速抗斷）
                    bt_payload = {
                        "timestamp": payload["timestamp"],
                        "speed": payload["speed"],
                        "tilt": payload["tilt"],
                        "speed_source": payload["speed_source"],
                        "exhibition": payload["exhibition"],
                        "warning": payload["warning"],
                        "radar_targets": payload["radar_targets"],
                        "system": payload["system"],
                        "recording": payload["recording"],
                        "trip": payload["trip"],
                        "hud_config": payload["hud_config"],
                        "app_data": payload["app_data"],
                        "alert": payload["alert"]
                    }
                    self.bt_server.broadcast(bt_payload)
                    
                    # 5. Local Visualization
                    if self.show_visual and frame is not None:
                        for r in detections or []:
                            bbox = r.get("bbox", [0, 0, 0, 0])
                            x1, y1, x2, y2 = [int(b) for b in bbox]
                            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                            cv2.putText(frame, f"{r.get('class', '?')} {r.get('confidence', 0):.2f}", (x1, y1-10), 
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                        
                        if warning:
                            color = (0, 0, 255) if warning.get("level") == "danger" else (0, 255, 255)
                            cv2.putText(frame, f"ALERT: {warning.get('message', '')}", (50, 50), 
                                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 3)

                        cv2.imshow("V.I.S.O.R. Core Monitor", frame)
                        if cv2.waitKey(1) & 0xFF == ord('q'):
                            self.running = False

                    # 6. Steady 20Hz Loop Timing Control (Dynamic compensation prevents clock drift & lag)
                    elapsed_iteration = time.time() - now
                    sleep_t = max(0.005, 0.050 - elapsed_iteration)
                    await asyncio.sleep(sleep_t)
                    
            except asyncio.CancelledError:
                print("Main loop cancelled.")
            finally:
                print("Stopping services...")
                self.reader_rear.stop()
                if self.reader_front:
                    self.reader_front.stop()
                self.udp_listener.stop()
                self.recorder.cleanup()
                self.executor.shutdown()
                self.bt_server.stop()
                self.trip_logger.cleanup()
                self.udp_broadcaster.close()

    def start(self):
        """
        入口點。
        """
        try:
            asyncio.run(self.main_loop())
        except KeyboardInterrupt:
            print("\n[INFO] 使用者手動中斷。")
        except Exception as e:
            import traceback
            print(f"\n[ERROR] 主控制器異常退出: {e}")
            traceback.print_exc()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="V.I.S.O.R. Main Controller")
    parser.add_argument("--demo", action="store_true", help="Enable Demo Mode (Loops videos and simulated sensors)")
    parser.add_argument("--exhibition", action="store_true", help="Enable Exhibition Demo Mode (Loops 32-sec scenario for HUD & App)")
    parser.add_argument("--source", type=str, help="Override video source (file path, stream URL, or camera index)")
    parser.add_argument("--visual", action="store_true", help="Show local CV2 window on Pi 5 screen")
    args = parser.parse_args()
    
    controller = MainController(video_source=args.source, demo_mode=args.demo, exhibition_mode=args.exhibition)
    controller.show_visual = args.visual
    controller.start()
