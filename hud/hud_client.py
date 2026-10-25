# hud_client.py — V.I.S.O.R. HUD for Pi Zero 2W + 1.3" OLED I2C (SH1106 / SSD1306 128x64)
import socket
import json
import time
import threading
import os
import sys
import math

from luma.core.interface.serial import i2c
from luma.oled.device import sh1106, ssd1306
from PIL import ImageFont, ImageDraw, Image

# ──────────────────────────────────────────────
# Screen & Geometry Constants (128x64)
# ──────────────────────────────────────────────
SCREEN_W = 128
SCREEN_H = 64

# Direction indicator symbols
ARROW = {
    "front": " /\\ ",
    "rear":  " \\/ ",
    "left":  " <  ",
    "right": "  > ",
}

class HudCanvas:
    """
    Context manager for HUD rendering with support for horizontal mirror,
    vertical flip, and custom transformations for helmet / HUD optical combiners.
    """
    def __init__(self, client):
        self.client = client
        self.image = Image.new("1", (SCREEN_W, SCREEN_H))
        self.draw = ImageDraw.Draw(self.image)

    def __enter__(self):
        return self.draw

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            return False
        img = self.image
        # 左右水平鏡像翻轉 (Mirror) - 確保安全帽光學反射時文字方向正確
        if getattr(self.client, 'mirror', True):
            img = img.transpose(Image.FLIP_LEFT_RIGHT)
        # 上下垂直翻轉 (Vertical Flip) - 確保安全帽仰角/俯角鏡像反射上下正確 (預設關閉，配合水平鏡像提供光學反射)
        if getattr(self.client, 'flip_v', False):
            img = img.transpose(Image.FLIP_TOP_BOTTOM)
        if self.client and self.client.device:
            try:
                self.client.device.display(img)
            except Exception:
                pass

class HudClient:
    """
    V.I.S.O.R. HUD Client for Pi Zero 2W + 1.3" OLED (SH1106 / SSD1306 I2C 128x64).
    
    Architecture:
      1. Network Thread: High-frequency UDP socket receiver (zero backlog).
      2. Render Thread: Steady 20-25 FPS refresh loop with hardware inversion alerts.
      3. Heartbeat Thread: Status reporting back to Pi 5 on port 5006.
    """

    def __init__(self, port=5005, target_fps=20, mirror=None, flip_v=None, rotate=None, model=None):
        self.port = port
        self.target_fps = target_fps
        self.frame_interval = 1.0 / target_fps
        self.running = True

        # Orientation: Mirror & Vertical Flip (Defaults to True for optical HUD visor reflection)
        env_mirror = os.environ.get("HUD_MIRROR")
        env_flip = os.environ.get("HUD_FLIP_V", os.environ.get("HUD_FLIP"))
        if env_mirror is not None and env_mirror.strip() != "":
            self.mirror = env_mirror.strip().lower() in ("1", "true", "yes")
        else:
            self.mirror = (mirror if mirror is not None else True)

        if env_flip is not None and env_flip.strip() != "":
            self.flip_v = env_flip.strip().lower() in ("1", "true", "yes")
        else:
            self.flip_v = (flip_v if flip_v is not None else False)

        self.rotate_val = int(os.environ.get("HUD_ROTATE", 0)) if rotate is None else int(rotate)

        # State and synchronization
        self.latest_data = {}
        self.data_lock = threading.Lock()
        self.last_received = 0.0
        self.timeout = 5.0  # seconds until "SIGNAL LOST" (容錯提升至 5 秒)

        # Alert flash state
        self.flash_state = False
        self.last_flash_time = 0.0
        self.flash_interval = 0.35  # seconds per flash toggle
        self.last_brightness = 200

        # OLED device instance and model preference
        # Defaults to SSD1306 for the currently connected 0.96" OLED (can switch to SH1106 via env/args/config)
        env_model = os.environ.get("OLED_MODEL", "SSD1306").strip().upper()
        if model:
            self.preferred_model = model.upper()
        elif env_model in ("SSD1306", "SH1106"):
            self.preferred_model = env_model
        else:
            self.preferred_model = "SSD1306"

        self.device = None
        self.device_model = "UNKNOWN"
        self.i2c_addr = 0x3C
        self.init_oled()

        # UDP Socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('0.0.0.0', self.port))
        self.sock.settimeout(0.5)

        # Fonts setup (Optimized for 128x64 OLED)
        self.font_speed = ImageFont.load_default()
        self.font_main  = ImageFont.load_default()
        self.font_tiny  = ImageFont.load_default()
        self.font_alert = ImageFont.load_default()
        self._load_fonts()

        # Pi 5 IP auto-discovery
        self.pi5_ip = None

    def _load_fonts(self):
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        ]
        for path in font_paths:
            if os.path.exists(path):
                try:
                    self.font_speed = ImageFont.truetype(path, 26)   # Large speed digits
                    self.font_main  = ImageFont.truetype(path, 11)   # Standard labels
                    self.font_tiny  = ImageFont.truetype(path, 9)    # Top/sub details
                    self.font_alert = ImageFont.truetype(path, 10)   # Threat banner
                    print(f"[INFO] Loaded TrueType fonts from: {path}")
                    return
                except Exception as e:
                    print(f"[WARN] Failed loading font {path}: {e}")

        print("[WARN] Using default bitmap fonts (install fonts-dejavu-core for best look)")

    # ──────────────────────────────────────────
    # OLED Hardware Detection (SSD1306 0.96" / SH1106 1.3")
    # ──────────────────────────────────────────
    def init_oled(self, preferred_model=None):
        """Detect and initialize OLED controller (SSD1306 for 0.96\" or SH1106 for 1.3\")."""
        if preferred_model:
            self.preferred_model = preferred_model.upper()

        if self.preferred_model == "SH1106":
            candidates = [
                ("SH1106", sh1106, 0x3C),
                ("SH1106", sh1106, 0x3D),
                ("SSD1306", ssd1306, 0x3C),
                ("SSD1306", ssd1306, 0x3D),
            ]
        else:
            candidates = [
                ("SSD1306", ssd1306, 0x3C),
                ("SSD1306", ssd1306, 0x3D),
                ("SH1106", sh1106, 0x3C),
                ("SH1106", sh1106, 0x3D),
            ]

        for model_name, driver_cls, addr in candidates:
            try:
                serial = i2c(port=1, address=addr)
                dev = driver_cls(serial, width=SCREEN_W, height=SCREEN_H, rotate=self.rotate_val)
                dev.contrast(200)
                self.device = dev
                self.device_model = model_name
                self.i2c_addr = addr
                size_str = "0.96\"" if model_name == "SSD1306" else "1.3\""
                print(f"[INFO] Successfully initialized {size_str} OLED ({model_name} @ 0x{addr:02X}, rotate={self.rotate_val}, mirror={self.mirror}, flip_v={self.flip_v})")
                return
            except Exception:
                pass

        print("[ERROR] Could not initialize any OLED device on I2C port 1 (0x3C/0x3D). Check wiring!")
        self.device = None

    def _ensure_device(self):
        if self.device is None:
            self.init_oled()
        return self.device is not None

    # ──────────────────────────────────────────
    # Main Engine
    # ──────────────────────────────────────────
    def start(self):
        size_str = "0.96\"" if self.device_model == "SSD1306" else "1.3\""
        print(f"[HUD] V.I.S.O.R. HUD starting on {size_str} OLED ({self.device_model}). Listening on UDP :{self.port}...")
        
        # Display splash boot screen
        self._boot_screen()

        # Start background receiver & heartbeat threads
        recv_thread = threading.Thread(target=self._network_receiver_loop, daemon=True)
        hb_thread   = threading.Thread(target=self._heartbeat_loop, daemon=True)
        recv_thread.start()
        hb_thread.start()

        # Main thread runs render loop at target FPS
        try:
            self._render_loop()
        except KeyboardInterrupt:
            print("\n[INFO] HUD shutting down gracefully...")
        finally:
            self.running = False
            if self.device:
                try:
                    self.device.clear()
                except Exception:
                    pass
            self.sock.close()

    # ──────────────────────────────────────────
    # Thread 1: Network Receiver (Zero Latency)
    # ──────────────────────────────────────────
    def _network_receiver_loop(self):
        while self.running:
            try:
                data, addr = self.sock.recvfrom(4096)
                payload = json.loads(data.decode('utf-8'))
                
                if addr and addr[0]:
                    self.pi5_ip = addr[0]

                # Handle system commands
                if payload.get("system_command") == "shutdown":
                    print("[CMD] Received shutdown command from Pi 5!")
                    self._show_text("POWERING OFF", "Shutting down...")
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
                            if os.system(cmd) == 0:
                                break
                        except Exception:
                            pass
                    self.running = False
                    break

                with self.data_lock:
                    self.latest_data = payload
                    self.last_received = time.time()

            except socket.timeout:
                continue
            except json.JSONDecodeError:
                continue
            except Exception as e:
                if self.running:
                    print(f"[NET ERROR] {e}")
                time.sleep(0.01)

    # ──────────────────────────────────────────
    # Thread 2: Render Loop (Smooth ~20-25 FPS)
    # ──────────────────────────────────────────
    def _render_loop(self):
        while self.running:
            start_t = time.time()

            with self.data_lock:
                data_copy = dict(self.latest_data)
                last_rx = self.last_received

            now = time.time()
            if last_rx == 0 or (now - last_rx > self.timeout):
                # If signal has been lost for over 10 seconds, enter standalone offline demo
                # so the helmet HUD stays active with dynamic animations during exhibitions
                if (now - last_rx > 10.0):
                    self._render_offline_demo(now)
                else:
                    self._render_lost_signal(now)
            else:
                self._render_telemetry(data_copy, now)

            elapsed = time.time() - start_t
            sleep_t = max(0.005, self.frame_interval - elapsed)
            time.sleep(sleep_t)

    # ──────────────────────────────────────────
    # Thread 3: Heartbeat Loop (5006 UDP)
    # ──────────────────────────────────────────
    def _heartbeat_loop(self):
        hb_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        hb_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        while self.running:
            size_str = "0.96\"" if self.device_model == "SSD1306" else "1.3\""
            payload = json.dumps({
                "device": "HUD",
                "display": f"{self.device_model} {size_str} (0x{self.i2c_addr:02X})",
                "timestamp": time.time(),
                "status": "active"
            }).encode('utf-8')

            targets = []
            if self.pi5_ip:
                targets.append(self.pi5_ip)
            else:
                targets.extend(['255.255.255.255', '192.168.4.1', '192.168.4.255'])
                try:
                    targets.append(socket.gethostbyname('pi5.local'))
                except Exception:
                    pass

            for target in set(targets):
                try:
                    hb_sock.sendto(payload, (target, 5006))
                except Exception:
                    pass

            time.sleep(2.0)

    # ──────────────────────────────────────────
    # Display Renderers
    # ──────────────────────────────────────────
    def _boot_screen(self):
        if not self._ensure_device():
            return
        try:
            size_str = "0.96\"" if self.device_model == "SSD1306" else "1.3\""
            with HudCanvas(self) as draw:
                draw.rectangle((0, 0, SCREEN_W - 1, SCREEN_H - 1), outline="white")
                draw.text((16, 8), "V.I.S.O.R.  HUD", fill="white", font=self.font_main)
                draw.text((8, 26), "SYSTEM INITIALIZING", fill="white", font=self.font_tiny)
                draw.text((12, 42), f"{size_str} OLED ({self.device_model})", fill="white", font=self.font_tiny)
        except Exception:
            self.device = None

    def _render_lost_signal(self, now):
        if not self._ensure_device():
            return
        # Reset inverted screen
        try:
            self.device.invert(False)
        except Exception:
            pass

        dots = "." * (int(now * 2) % 4)
        try:
            with HudCanvas(self) as draw:
                draw.rectangle((0, 0, SCREEN_W - 1, 11), fill="white")
                draw.text((4, 1), "V.I.S.O.R. OFFLINE", fill="black", font=self.font_tiny)
                
                draw.text((16, 22), "SIGNAL LOST", fill="white", font=self.font_main)
                draw.text((10, 42), f"Waiting Pi 5{dots}", fill="white", font=self.font_tiny)
        except Exception:
            self.device = None

    def _render_offline_demo(self, now):
        """Dynamic offline animation loop for exhibition/testing when Pi 5 is offline."""
        # 24-second autonomous scenario cycle
        t_phase = now % 24.0
        if t_phase < 6.0:
            # Phase 1: Accelerating smoothly
            spd = int(25 + (t_phase / 6.0) * 45)
            tilt = int(-3 * (t_phase / 6.0))
            warn = None
            cam = None
        elif t_phase < 12.0:
            # Phase 2: Left blind spot alert
            sub_t = t_phase - 6.0
            spd = 68
            tilt = -6
            dist = max(3.2, 8.5 - sub_t * 0.9)
            warn = {
                "direction": "left",
                "level": "danger" if dist < 4.5 else "warning",
                "dist": dist,
                "class_name": "CAR"
            }
            cam = None
        elif t_phase < 17.0:
            # Phase 3: Mountain curve leaning right
            sub_t = t_phase - 12.0
            spd = int(72 - sub_t * 2)
            tilt = int(12 + math.sin(sub_t * 1.2) * 14)
            warn = None
            cam = None
        elif t_phase < 21.0:
            # Phase 4: Right blind spot scooter danger + speed camera
            sub_t = t_phase - 17.0
            spd = int(55 - sub_t * 3)
            tilt = 4
            dist = max(2.1, 5.5 - sub_t * 0.8)
            warn = {
                "direction": "right",
                "level": "danger",
                "dist": dist,
                "class_name": "SCOOTER"
            }
            cam = {"limit": 50, "distance": int(max(30, 110 - sub_t * 20))}
        else:
            # Phase 5: Deceleration to stop
            sub_t = t_phase - 21.0
            spd = max(0, int(42 - sub_t * 14))
            tilt = 0
            warn = None
            cam = None

        demo_data = {
            "speed": spd,
            "tilt": tilt,
            "warning": warn,
            "app_data": {
                "speed": spd,
                "tilt": tilt,
                "cameraAlert": cam
            },
            "system": {
                "cpu": 18,
                "temp": 41.5
            },
            "hud_config": {
                "speed": True,
                "camera": True,
                "nav": True,
                "time": True,
                "brightness": 200,
                "mirror": self.mirror,
                "flip_v": self.flip_v
            }
        }
        self._render_telemetry(demo_data, now, is_demo_overlay=True)

    def _show_text(self, line1, line2=""):
        if not self._ensure_device():
            return
        try:
            with HudCanvas(self) as draw:
                draw.text((4, 16), line1, fill="white", font=self.font_main)
                if line2:
                    draw.text((4, 36), line2, fill="white", font=self.font_tiny)
        except Exception:
            self.device = None

    def _render_telemetry(self, data, now, is_demo_overlay=False):
        if not self._ensure_device():
            return

        try:
            # 1. Config & Contrast & Orientation Sync
            config = data.get("hud_config", {
                "speed": True, "camera": True, "nav": True, "time": True, "brightness": 200
            })

            # Dynamic OLED model switch if directed by Pi 5 config
            desired_model = config.get("oled_model")
            if desired_model and desired_model.upper() in ("SSD1306", "SH1106") and desired_model.upper() != self.device_model:
                print(f"[HUD] Received dynamic display switch: {self.device_model} -> {desired_model.upper()}")
                self.init_oled(desired_model.upper())
                if not self._ensure_device():
                    return

            new_bright = int(config.get("brightness", 200))
            if new_bright != self.last_brightness:
                self.device.contrast(new_bright)
                self.last_brightness = new_bright

            # Dynamic orientation toggle from Pi 5 / App (確保鏡像 mirror 與上下反轉 flip_v 均生效)
            if "mirror" in config and config["mirror"] is not None:
                self.mirror = bool(config["mirror"])
            else:
                self.mirror = True

            if "flip_v" in config and config["flip_v"] is not None:
                self.flip_v = bool(config["flip_v"])
            elif "flip" in config and config["flip"] is not None:
                self.flip_v = bool(config["flip"])
            else:
                self.flip_v = False

            # 2. Flash state toggle
            if now - self.last_flash_time >= self.flash_interval:
                self.flash_state = not self.flash_state
                self.last_flash_time = now

            # 3. Extract telemetry
            app_data  = data.get("app_data", {})
            speed     = int(app_data.get("speed", data.get("speed", 0)))
            tilt      = int(app_data.get("tilt",  data.get("tilt",  0)))
            warning   = data.get("warning")
            cam_alert = app_data.get("cameraAlert")
            is_exhibition = is_demo_overlay or (data.get("speed_source") == "exhibition") or bool(data.get("exhibition"))

            # 4. Hardware full-screen invert on critical danger (safe fallback)
            is_danger = bool(warning and warning.get("level") == "danger")
            if hasattr(self.device, 'invert'):
                try:
                    self.device.invert(is_danger and self.flash_state)
                except Exception:
                    pass
            elif hasattr(self.device, 'command'):
                try:
                    self.device.command(0xA7 if (is_danger and self.flash_state) else 0xA6)
                except Exception:
                    pass

            with HudCanvas(self) as draw:
                # ── Top Bar (Y: 0-11) ──────────────────────────
                if is_exhibition:
                    draw.text((2, 1), "V.I.S.O.R. DEMO", fill="white", font=self.font_tiny)
                else:
                    draw.text((2, 1), "V.I.S.O.R.", fill="white", font=self.font_tiny)
                
                # Active link dot
                draw.ellipse((58, 4, 62, 8), fill="white" if self.flash_state else "black", outline="white")
                
                if config.get("time", True):
                    t_str = time.strftime("%H:%M")
                    draw.text((SCREEN_W - 28, 1), t_str, fill="white", font=self.font_tiny)
                draw.line((0, 12, SCREEN_W, 12), fill="white")

                # ── 左右兩側盲點警示燈 (Side Blind Spot Indicators) ───────
                direction = (warning.get("direction", "") if warning else "").lower()
                dist_val = warning.get("dist", 0) if warning else 0
                dist_str = f"{dist_val:.1f}m" if isinstance(dist_val, (int, float)) and dist_val > 0 else ""
                
                # 左側盲點燈 (Left BSD)
                if direction == "left":
                    if self.flash_state or is_danger:
                        # 繪製左側高亮雙箭頭 ◀◀
                        draw.polygon([(0, 20), (6, 14), (6, 26)], fill="white")
                        draw.polygon([(4, 34), (10, 28), (10, 40)], fill="white")
                        draw.rectangle((0, 14, 2, 40), fill="white")
                
                # 右側盲點燈 (Right BSD)
                if direction == "right":
                    if self.flash_state or is_danger:
                        # 繪製右側高亮雙箭頭 ▶▶
                        draw.polygon([(127, 20), (121, 14), (121, 26)], fill="white")
                        draw.polygon([(123, 34), (117, 28), (117, 40)], fill="white")
                        draw.rectangle((125, 14, 127, 40), fill="white")

                # ── Speed Center Area (Y: 14-42) ───────────────
                if config.get("speed", True):
                    s_str = str(speed)
                    char_w = 16 if speed < 10 else (13 if speed < 100 else 11)
                    x_spd = max(14, (SCREEN_W - len(s_str) * char_w) // 2 - 6)
                    draw.text((x_spd, 13), s_str, fill="white", font=self.font_speed)
                    
                    # km/h unit label
                    unit_x = x_spd + len(s_str) * char_w + 3
                    draw.text((min(unit_x, SCREEN_W - 26), 28), "km/h", fill="white", font=self.font_tiny)

                # ── Lean Angle (Left, Y: 43-52) ────────────────
                tilt_sign = "+" if tilt > 0 else ("-" if tilt < 0 else "")
                tilt_str = f"{tilt_sign}{abs(tilt)} deg"
                draw.text((4, 43), tilt_str, fill="white", font=self.font_tiny)

                # ── Speed Camera Alert (Right, Y: 43-52) ───────
                if config.get("camera", True) and cam_alert:
                    cam_limit = cam_alert.get("limit", 0)
                    cam_dist  = int(cam_alert.get("distance", 0))
                    cam_label = f"CAM {cam_limit} | {cam_dist}m"

                    if self.flash_state:
                        w_cam = 74
                        draw.rectangle((SCREEN_W - w_cam, 42, SCREEN_W - 1, 52), fill="white", outline="white")
                        draw.text((SCREEN_W - w_cam + 2, 43), cam_label, fill="black", font=self.font_tiny)
                    else:
                        draw.text((SCREEN_W - 72, 43), cam_label, fill="white", font=self.font_tiny)

                # ── Separator Line ────────────────────────────
                draw.line((0, 53, SCREEN_W, 53), fill="white")

                # ── Threat Alert Banner (Bottom, Y: 54-63) ────
                if warning:
                    cls_name = (warning.get("class_name") or "VEHICLE").upper()
                    
                    if direction == "front":
                        badge_txt = f"^ FCW {cls_name} {dist_str}".strip()
                    elif direction == "rear":
                        badge_txt = f"v BSD {cls_name} {dist_str}".strip()
                    elif direction == "left":
                        badge_txt = f"< LEFT BSD {cls_name} {dist_str}".strip()
                    elif direction == "right":
                        badge_txt = f"> RIGHT BSD {cls_name} {dist_str}".strip()
                    else:
                        badge_txt = f"! ALERT {dist_str}".strip()

                    if is_danger:
                        # 🔴 一級危險：實心反白全寬警示橫幅
                        draw.rectangle((0, 53, SCREEN_W - 1, SCREEN_H - 1), fill="white", outline="white")
                        draw.text((4, 54), f"[!] {badge_txt}"[:22], fill="black", font=self.font_alert)
                    else:
                        # 🟡 二級注意：鏤空黑底線框警示橫幅
                        draw.rectangle((0, 53, SCREEN_W - 1, SCREEN_H - 1), fill="black", outline="white")
                        draw.text((4, 54), badge_txt[:22], fill="white", font=self.font_alert)
                else:
                    # Normal Telemetry: Pi 5 CPU% and Temperature
                    sys_info = data.get("system", {})
                    try:
                        cpu  = float(sys_info.get("cpu", 0) or 0)
                        temp = float(sys_info.get("temp", 0) or 0)
                    except Exception:
                        cpu, temp = 0.0, 0.0
                    lane_info = data.get("lanes", {})
                    
                    if lane_info and ("left" in lane_info or "right" in lane_info):
                        status_line = f"LANE TRACKING  {cpu:.0f}%"
                    else:
                        status_line = f"CPU {cpu:.0f}%  TEMP {temp:.1f}C"
                    draw.text((4, 54), status_line, fill="white", font=self.font_tiny)

        except Exception as e:
            print(f"[RENDER ERROR] {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="V.I.S.O.R. HUD Client (Pi Zero 2W + 0.96\"/1.3\" OLED)")
    parser.add_argument("--port", type=int, default=5005, help="UDP listening port")
    parser.add_argument("--model", type=str, default=None, choices=["SSD1306", "SH1106"], help="Force OLED model (SSD1306 for 0.96\", SH1106 for 1.3\")")
    parser.add_argument("--mirror", dest="mirror", action="store_true", default=None, help="Force mirror display horizontally")
    parser.add_argument("--no-mirror", dest="mirror", action="store_false", help="Disable horizontal mirror")
    parser.add_argument("--flip", dest="flip_v", action="store_true", default=None, help="Force flip display vertically")
    parser.add_argument("--no-flip", dest="flip_v", action="store_false", help="Disable vertical flip")
    parser.add_argument("--rotate", type=int, default=None, choices=[0, 1, 2, 3], help="Hardware rotation (0, 1, 2, 3)")
    args = parser.parse_args()

    client = HudClient(port=args.port, mirror=args.mirror, flip_v=args.flip_v, rotate=args.rotate, model=args.model)
    client.start()
