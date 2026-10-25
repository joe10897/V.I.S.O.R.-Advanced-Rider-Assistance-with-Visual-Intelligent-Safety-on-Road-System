import cv2
import time
import threading
import queue
import subprocess
import numpy as np
import os
import glob

try:
    from picamera2 import Picamera2
except ImportError:
    Picamera2 = None

def detect_pi5_mipi_cameras():
    """自動快速偵測 Pi 5 實體連接的 MIPI-CSI 相機索引清單 (0, 1)"""
    detected = []
    try:
        res = subprocess.run(["rpicam-hello", "--list-cameras"], capture_output=True, text=True, timeout=1.5)
        for line in (res.stdout + res.stderr).split("\n"):
            line = line.strip()
            if line and line[0].isdigit() and ":" in line:
                try:
                    idx = int(line.split(":")[0].strip())
                    detected.append(idx)
                except Exception:
                    pass
    except Exception:
        pass
    return detected

def check_is_capture_device(dev_path):
    """
    透過 Linux V4L2 核心 ioctl (VIDIOC_QUERYCAP) 精確判定是否為真實影像擷取端點
    徹底過濾掉 UVC Metadata 節點 (V4L2_CAP_META_CAPTURE) 與非 capture 端點
    """
    try:
        import fcntl
        import struct
        fd = os.open(dev_path, os.O_RDONLY | os.O_NONBLOCK)
        try:
            buf = bytearray(104)
            # VIDIOC_QUERYCAP = 0x80685600
            fcntl.ioctl(fd, 0x80685600, buf)
            driver, card, bus_info, version, capabilities, device_caps = struct.unpack("16s32s32sIII12x", buf)
            card_str = card.decode("utf-8", errors="ignore").strip("\x00 ").strip()
            bus_str = bus_info.decode("utf-8", errors="ignore").strip("\x00 ").strip()
            caps = device_caps if (capabilities & 0x80000000) else capabilities
            is_capture = bool(caps & 0x00000001)
            is_meta = bool(caps & 0x00800000)
            return (is_capture and not is_meta), card_str, bus_str
        finally:
            os.close(fd)
    except Exception:
        try:
            c = cv2.VideoCapture(dev_path, cv2.CAP_V4L2)
            if not c.isOpened():
                c = cv2.VideoCapture(dev_path)
            if c.isOpened():
                ret, _ = c.read()
                c.release()
                return ret, "USB Camera", dev_path
        except Exception:
            pass
        return False, "", ""

def find_usb_cameras():
    """搜尋系統中可用的 USB / V4L2 相機節點 (/dev/video*)，依編號數值排序並過濾出真正的 USB 影像串流端點"""
    def _dev_num(p):
        try:
            return int(os.path.basename(p).replace("video", ""))
        except Exception:
            return 999
            
    all_nodes = sorted(glob.glob("/dev/video*"), key=_dev_num)
    usb_streaming_nodes = []
    seen_buses = set()
    
    for n in all_nodes:
        node_name = os.path.basename(n)
        sys_path = f"/sys/class/video4linux/{node_name}"
        dev_link = f"{sys_path}/device"
        
        # 檢查是否為實體 USB 設備 (排除 Pi 5 內部 rp1-cfe / ISP 虛擬節點)
        is_usb_hw = False
        if os.path.exists(dev_link):
            try:
                target_path = os.path.realpath(dev_link).lower()
                if "usb" in target_path:
                    is_usb_hw = True
            except Exception:
                pass
                
        if not is_usb_hw:
            continue
            
        is_capture, card_name, bus_info = check_is_capture_device(n)
        if is_capture:
            # 依據硬體 bus_info 過濾同一鏡頭的多個 capture 節點 (避免同鏡頭重複採樣)
            bus_key = bus_info if bus_info else n
            if bus_key in seen_buses:
                continue
            seen_buses.add(bus_key)
            usb_streaming_nodes.append(n)
            
    return usb_streaming_nodes

class FrameReader:
    """
    V.I.S.O.R. 專用鏡頭串流讀取器
    - 支援 Sony IMX662 STARVIS 2 雙 USB2.0 鏡頭 (前 120° / 後 173°，直連 V4L2 + MJPG 硬體解碼，純 USB 免 I2C)
    - 零緩衝模式 (cap.set(BUFFERSIZE, 1))：徹底消除 V4L2 排隊延遲，維持即時 30 FPS 最新影格
    - 完全非同步啟動 (Non-blocking)，線路鬆脫時自動降級至待機保護，絕不卡死主系統
    """
    def __init__(self, video_source, width=640, height=480, rotate=0, camera_type=None, role="auto"):
        self.video_source = video_source
        self.width = width
        self.height = height
        self.rotate = rotate  # 0, 90, 180, 270
        self.camera_type = camera_type  # 'csi', 'usb', 'file' or None (auto)
        
        # 角色判定：前鏡頭 (front) 或後鏡頭 (rear)，防止單鏡頭時後鏡頭誤挪用前鏡頭硬體節點
        if role == "auto":
            src_str = str(video_source).lower()
            if "rear" in src_str or src_str in ("/dev/video2", "2", "usb1"):
                self.role = "rear"
            elif "front" in src_str or src_str in ("/dev/video0", "0", "usb0", "usb"):
                self.role = "front"
            else:
                self.role = "auto"
        else:
            self.role = role
        
        self.proc = None
        self.cap = None
        self.picam2 = None
        self.actual_source = str(video_source)
        self.is_dummy = True
        self.is_hardware_connected = False
        self.last_reconnect_attempt = 0.0
        
        # 佇列與執行緒
        self.q = queue.Queue(maxsize=1)
        self.stopped = False
        self.init_lock = threading.Lock()
        
        # 預先生成高質感待機影格
        self.standby_frame = self._generate_standby_frame()
        self.q.put(self.standby_frame.copy())
        
        self.thread = threading.Thread(target=self.run, daemon=True)
        print(f"[FrameReader] 初始化鏡頭來源: {video_source} (type={camera_type or 'auto'}, 規格={width}x{height}, 旋轉={rotate}°)")

    def _generate_standby_frame(self):
        """生成車載待機/連線中專用影格"""
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        # 背景微藍深灰色
        frame[:] = (18, 18, 24)
        
        # 邊框裝飾
        cv2.rectangle(frame, (10, 10), (self.width - 10, self.height - 10), (50, 60, 70), 1)
        
        # 文字標註
        src_label = str(self.video_source)
        if str(src_label).startswith("/dev/video") or self.camera_type == "usb":
            src_desc = f"USB2.0 SONY IMX662 ({src_label})"
        elif str(src_label) in ("0", "1") or isinstance(src_label, int):
            src_desc = f"MIPI-CSI SENSOR {src_label}"
        else:
            src_desc = f"SOURCE: {src_label}"
            
        cv2.putText(frame, "V.I.S.O.R. OPTICAL FEED", (24, 40), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 255), 2)
        cv2.putText(frame, f"STATUS: STANDBY / ACQUIRING", (24, 75), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1)
        cv2.putText(frame, f"DEVICE: {src_desc}", (24, 105), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (120, 140, 150), 1)
        cv2.putText(frame, f"RESOLUTION: {self.width}x{self.height} @ 30FPS (NO I2C)", (24, 130), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (90, 100, 110), 1)
        return frame

    def start(self):
        if not self.thread.is_alive():
            self.thread.start()

    def _open_usb_camera(self, dev_path_or_idx):
        """專用 USB / V4L2 鏡頭開啟函式 (針對 Sony IMX662 STARVIS 2 最佳化，以整數索引消除警告，零緩衝低延遲)"""
        print(f"[FrameReader] 正在以 V4L2 模式開啟 USB 鏡頭: {dev_path_or_idx} (Sony IMX662 STARVIS 2)")
        try:
            # 轉換為整數索引，徹底避免 OpenCV V4L2 後端 'can't be used to capture by name' 警告
            if isinstance(dev_path_or_idx, int):
                idx = dev_path_or_idx
            elif str(dev_path_or_idx).isdigit():
                idx = int(dev_path_or_idx)
            elif isinstance(dev_path_or_idx, str) and dev_path_or_idx.startswith("/dev/video"):
                try:
                    idx = int(dev_path_or_idx.replace("/dev/video", ""))
                except Exception:
                    idx = dev_path_or_idx
            else:
                idx = 0
                
            dev_str = f"/dev/video{idx}" if isinstance(idx, int) else str(dev_path_or_idx)
            try:
                subprocess.run([
                    "v4l2-ctl", "-d", dev_str,
                    "--set-fmt-video=width=640,height=480,pixelformat=MJPG",
                    "--set-parm=30"
                ], capture_output=True, timeout=1.0)
                subprocess.run([
                    "v4l2-ctl", "-d", dev_str,
                    "--set-ctrl=exposure_auto_priority=0"
                ], capture_output=True, timeout=0.5)
            except Exception:
                pass

            cap = cv2.VideoCapture(idx, cv2.CAP_V4L2)
            if not cap.isOpened() and isinstance(dev_path_or_idx, str):
                cap = cv2.VideoCapture(dev_path_or_idx)
                
            if cap.isOpened():
                # 啟用 MJPG 硬體編碼解壓縮，節省 USB 2.0 頻寬並維持 30 FPS
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                cap.set(cv2.CAP_PROP_FPS, 30)
                # 零緩衝模式：消除 OpenCV V4L2 預設 4 影格核心排隊延遲，維持最新影格
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                
                # 測試讀取單影格
                ret, test_f = cap.read()
                if ret and test_f is not None and test_f.size > 0:
                    self.cap = cap
                    self.is_dummy = False
                    self.is_hardware_connected = True
                    self.actual_source = f"USB-IMX662({dev_path_or_idx})"
                    print(f"[INFO] [OK] 成功啟用 USB IMX662 車載鏡頭 ({dev_path_or_idx})！(MJPG 640x480@30fps, 零延遲模式)")
                    return True
                else:
                    cap.release()
        except Exception as e:
            print(f"[WARN] USB 鏡頭開啟失敗 ({dev_path_or_idx}): {e}")
        return False

    def _open_mipi_csi_camera(self, source_idx):
        """Pi 5 MIPI-CSI 專用相機管線 (Picamera2 優先 -> rpicam-vid 隔離 -> V4L2 備援)"""
        # 1. Picamera2 原生加速模式
        if Picamera2 is not None:
            try:
                p2 = Picamera2(camera=source_idx)
                p2_config = p2.create_preview_configuration(main={"size": (self.width, self.height), "format": "BGR888"})
                p2.configure(p2_config)
                p2.start()
                time.sleep(0.3)
                test_f = p2.capture_array()
                if test_f is not None and test_f.size > 0:
                    self.picam2 = p2
                    self.is_dummy = False
                    self.is_hardware_connected = True
                    self.actual_source = f"Picamera2({source_idx})"
                    print(f"[INFO] [OK] 成功啟用 Picamera2 原生硬體加速 (Sensor {source_idx})！")
                    return True
            except Exception as e:
                print(f"[INFO] Picamera2 略過或由系統接管 ({e})，切換至背景管線...")
                if self.picam2:
                    try:
                        self.picam2.stop()
                        self.picam2.close()
                    except Exception:
                        pass
                    self.picam2 = None

        # 2. rpicam-vid 背景獨立管線
        port = 8000 + int(source_idx)
        tx_url = f"udp://127.0.0.1:{port}"
        rx_url = f"udp://127.0.0.1:{port}?overrun_nonfatal=1&fifo_size=50000000"
        
        cmd = [
            "rpicam-vid", "-n", "-t", "0", "--camera", str(source_idx),
            "--width", str(self.width), "--height", str(self.height), "--framerate", "30",
            "--codec", "mjpeg", "--inline",
            "--awb", "auto", "--metering", "matrix",
            "--exposure", "sport", "--denoise", "cdn_fast",
            "-o", tx_url
        ]
        try:
            self.proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            time.sleep(1.0)
            for _ in range(4):
                if self.proc and self.proc.poll() is not None:
                    break
                try:
                    cap = cv2.VideoCapture(rx_url, cv2.CAP_FFMPEG)
                    if cap.isOpened():
                        self.cap = cap
                        self.is_dummy = False
                        self.is_hardware_connected = True
                        self.actual_source = tx_url
                        print(f"[INFO] [OK] 成功啟用 rpicam-vid 硬體 MJPEG 串流 ({source_idx})！")
                        return True
                except Exception:
                    pass
                time.sleep(0.3)
        except Exception as e:
            print(f"[WARN] 無法執行 rpicam-vid: {e}")
            self.proc = None

        # 3. 回退至 V4L2 模式
        try:
            if self.proc:
                try:
                    os.killpg(os.getpgid(self.proc.pid), 15)
                except Exception:
                    pass
                self.proc = None
            cap = cv2.VideoCapture(int(source_idx), cv2.CAP_V4L2)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            if cap.isOpened():
                ret, _ = cap.read()
                if ret:
                    self.cap = cap
                    self.is_dummy = False
                    self.is_hardware_connected = True
                    self.actual_source = f"V4L2({source_idx})"
                    print(f"[INFO] [OK] 成功啟用 V4L2 備援模式 ({source_idx})！")
                    return True
                cap.release()
        except Exception:
            pass

        return False

    def _attempt_connection(self):
        """非同步嘗試開啟鏡頭硬體"""
        with self.init_lock:
            src = self.video_source
            
            # A. 判斷為 USB 鏡頭來源 (純 USB 模式，完全跳過任何 I2C/CSI 探測)
            is_usb = (
                self.camera_type == "usb" or
                (isinstance(src, str) and (src.startswith("/dev/video") or "usb" in src.lower()))
            )
            if is_usb:
                target_dev = src
                nodes = find_usb_cameras()
                
                # 嚴格依據角色 (front / rear) 分配硬體端點，徹底根除單鏡頭時後鏡頭誤開啟前鏡頭的幽靈後方警示
                if self.role == "rear":
                    if str(src).startswith("/dev/video") and str(src) in nodes:
                        target_dev = src
                    elif len(nodes) >= 2:
                        target_dev = nodes[1]
                    elif str(src).startswith("/dev/video") and os.path.exists(str(src)):
                        target_dev = src
                    else:
                        print(f"[FrameReader] ℹ️ 實體 USB 鏡頭僅偵測到 {len(nodes)} 組 ({nodes[0] if nodes else '無'})，保留給前向視角。後鏡頭未連接實體硬體，維持 Standby 待機保護。")
                        self.is_dummy = True
                        self.is_hardware_connected = False
                        return False
                elif self.role == "front":
                    if str(src).startswith("/dev/video") and str(src) in nodes:
                        target_dev = src
                    elif nodes:
                        target_dev = nodes[0]
                    elif str(src).startswith("/dev/video") and os.path.exists(str(src)):
                        target_dev = src
                    else:
                        self.is_dummy = True
                        self.is_hardware_connected = False
                        return False
                else:
                    if src in ("usb", "usb0", "front", "0") and self.camera_type == "usb":
                        target_dev = nodes[0] if nodes else None
                    elif src in ("usb1", "rear", "1", "2") and self.camera_type == "usb":
                        target_dev = nodes[1] if len(nodes) > 1 else None
                    elif src in ("usb", "usb0"):
                        target_dev = nodes[0] if nodes else None
                    elif src == "usb1":
                        target_dev = nodes[1] if len(nodes) > 1 else None
                    
                    # 智慧防呆：若 config 寫死 /dev/video0 或 /dev/video2 (舊 CSI/PiSP 殘留)，自動指派至偵測到的真實 USB 鏡頭
                    if target_dev in ("/dev/video0", "0", 0) and nodes and "/dev/video0" not in nodes:
                        target_dev = nodes[0]
                    elif target_dev in ("/dev/video2", "2", 2) and nodes and "/dev/video2" not in nodes:
                        target_dev = nodes[1] if len(nodes) > 1 else None
                    
                if target_dev is None:
                    return False
                return self._open_usb_camera(target_dev)

            # B. 判斷為 CSI 索引 (0 或 1) - 僅在非 USB 且未停用 I2C 時執行
            is_csi = (
                self.camera_type == "csi" or
                (self.camera_type not in ("usb", "file") and (isinstance(src, int) or (isinstance(src, str) and str(src).isdigit())))
            )
            if is_csi:
                source_idx = int(src)
                return self._open_mipi_csi_camera(source_idx)

            # C. 影片檔案或 RTSP/HTTP 網路串流
            try:
                cap = cv2.VideoCapture(src)
                if cap.isOpened():
                    self.cap = cap
                    self.is_dummy = False
                    self.is_hardware_connected = True
                    print(f"[INFO] [OK] 成功開啟影音來源: {src}")
                    return True
            except Exception as e:
                print(f"[WARN] 無法開啟串流 {src}: {e}")

            self.is_dummy = True
            self.is_hardware_connected = False
            return False

    def run(self):
        # 1. 首次非同步嘗試開啟
        self._attempt_connection()
        
        frame_idx = 0
        while not self.stopped:
            # 若目前為待機模式，定時在背景嘗試重新連線 (每 4 秒一次)
            if self.is_dummy:
                now = time.time()
                if now - self.last_reconnect_attempt > 4.0:
                    self.last_reconnect_attempt = now
                    # 嘗試靜默重連實體鏡頭
                    if self._attempt_connection():
                        continue
                
                # 輸出帶有動態呼吸點的待機影格，確保主迴圈維持 30 FPS 節奏
                time.sleep(0.033)
                frame_idx += 1
                if not self.q.full():
                    dyn_frame = self.standby_frame.copy()
                    # 待機閃爍綠/藍心跳指示點
                    pulse_color = (0, 255, 128) if (frame_idx % 30 < 15) else (40, 60, 80)
                    cv2.circle(dyn_frame, (self.width - 24, 24), 6, pulse_color, -1)
                    self.q.put(dyn_frame)
                continue

            # 正常讀取實體鏡頭畫面
            try:
                frame = None
                if self.picam2:
                    frame = self.picam2.capture_array()
                elif self.cap:
                    ret, f = self.cap.read()
                    if ret and f is not None and f.size > 0:
                        frame = f
                    else:
                        # 實體鏡頭掉幀或斷線 (如 200cm 排線接觸不良)
                        print(f"[WARN] 鏡頭 {self.video_source} 讀取中斷，切換至保護待機模式並背景重連...")
                        self.is_dummy = True
                        self.is_hardware_connected = False
                        if self.cap:
                            try: self.cap.release()
                            except Exception: pass
                            self.cap = None
                        continue

                if frame is None:
                    time.sleep(0.01)
                    continue

                # 畫面旋轉校正 (0, 90, 180, 270)
                if self.rotate == 180:
                    frame = cv2.rotate(frame, cv2.ROTATE_180)
                elif self.rotate == 90:
                    frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
                elif self.rotate == 270:
                    frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)

                # 確保佇列永遠為最新影格 (Zero-latency drop)
                if self.q.full():
                    try:
                        self.q.get_nowait()
                    except queue.Empty:
                        pass
                self.q.put(frame)
            except Exception as e:
                # 擷取異常時容錯降級
                self.is_dummy = True
                time.sleep(0.03)

    def get_frame_properties(self):
        if self.picam2:
            return self.width, self.height
        if self.cap and not self.is_dummy:
            w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            if w > 0 and h > 0:
                return w, h
        return self.width, self.height

    def read(self, timeout=0.05):
        try:
            return self.q.get(timeout=timeout)
        except queue.Empty:
            return None

    def stop(self):
        self.stopped = True
        if self.picam2:
            try:
                self.picam2.stop()
                self.picam2.close()
            except Exception:
                pass
            self.picam2 = None
        if self.cap:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None
        if self.proc:
            try:
                os.killpg(os.getpgid(self.proc.pid), 9)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
            self.proc = None
