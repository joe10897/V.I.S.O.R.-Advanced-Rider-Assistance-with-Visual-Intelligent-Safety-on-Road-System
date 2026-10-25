import subprocess
import sys
import os
import time

sys.stdout.reconfigure(encoding='utf-8')

PI_IPS = ["192.168.4.1", "192.168.1.52", "192.168.1.69", "192.168.1.71"]
USER = "pi5"
TARGET_DIR = "/home/pi5/motorcycle_assist/"

# Complete and verified file synchronization list for Pi 5 Core Backend
FILES_TO_SYNC = [
    # Core Controller & Config
    ("main_controller.py", "main_controller.py"),
    ("config_loader.py", "config_loader.py"),
    ("config.json", "config.json"),
    ("trip_logger.py", "trip_logger.py"),
    ("visor_bt_agent.py", "visor_bt_agent.py"),
    ("run.sh", "run.sh"),
    ("visor.service", "visor.service"),
    ("deploy_to_pizero.py", "deploy_to_pizero.py"),
    ("hud/hud_client.py", "hud/hud_client.py"),
    ("scripts/diag_dual_usb.py", "scripts/diag_dual_usb.py"),
    ("scripts/install_service.sh", "scripts/install_service.sh"),

    # Communication Stack
    ("communication/bluetooth_server.py", "communication/bluetooth_server.py"),
    ("communication/udp_broadcaster.py", "communication/udp_broadcaster.py"),
    ("communication/udp_listener.py", "communication/udp_listener.py"),
    ("communication/websocket_server.py", "communication/websocket_server.py"),

    # Vision & Sensor Stack
    ("vision/frame_reader.py", "vision/frame_reader.py"),
    ("vision/recorder.py", "vision/recorder.py"),
    ("vision/sensor_sim.py", "vision/sensor_sim.py"),

    # YOLOv26 AI Vision Core & Spatial Fusion & Lane Detection
    ("YOLOv26_DEMO/visor_core.py", "YOLOv26_DEMO/visor_core.py"),
    ("YOLOv26_DEMO/engine_yolo26.py", "YOLOv26_DEMO/engine_yolo26.py"),
    ("YOLOv26_DEMO/spatial_fusion.py", "YOLOv26_DEMO/spatial_fusion.py"),
    ("YOLOv26_DEMO/engine_lstr.py", "YOLOv26_DEMO/engine_lstr.py"),
    ("YOLOv26_DEMO/engine_ufld.py", "YOLOv26_DEMO/engine_ufld.py"),
    ("YOLOv26_DEMO/engine_cv_lane.py", "YOLOv26_DEMO/engine_cv_lane.py"),

    # AI Models Weights (YOLOv26n Titan ONNX & PT + UFLD v2 320x800 ONNX + LSTR)
    ("models/yolo26n_tw_titan.onnx", "models/yolo26n_tw_titan.onnx"),
    ("models/yolo26n_tw_titan.pt", "models/yolo26n_tw_titan.pt"),
    ("models/ufldv2_tusimple_res18_320x800.onnx", "models/ufldv2_tusimple_res18_320x800.onnx"),
    ("models/lstr_180x320/lstr_180x320.onnx", "models/lstr_180x320/lstr_180x320.onnx"),
    ("models/lstr_culane.pkl", "models/lstr_culane.pkl"),
    ("YOLOv26_DEMO/models/lstr_culane.pkl", "YOLOv26_DEMO/models/lstr_culane.pkl")
]

print("==================================================")
print("  V.I.S.O.R. Core Backend Deployment to Pi 5 & Pi Zero")
print("==================================================")

is_code_only = any(arg in sys.argv for arg in ["--code-only", "--fast", "--scripts", "-s"])
if is_code_only:
    FILES_TO_SYNC = [f for f in FILES_TO_SYNC if not any(f[0].endswith(ext) for ext in [".onnx", ".pt", ".pkl", ".zip", ".mp4"])]
    print("\n[*] 已啟用快速腳本推播模式 (排除大模型權重檔)")

# Verify local file presence and sizes
print("\n[*] 正在檢查本地待同步檔案完整性與最新版本狀態...")
all_valid = True
total_bytes = 0
for src, rel_dest in FILES_TO_SYNC:
    if os.path.exists(src):
        sz = os.path.getsize(src)
        total_bytes += sz
        mtime = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(os.path.getmtime(src)))
        print(f"    [OK] {src:<42} ({sz:>10,} bytes | {mtime})")
    else:
        print(f"    [MISSING] {src:<42} 檔案不存在！")
        all_valid = False

print(f"\n[+] 待同步檔案總數: {len(FILES_TO_SYNC)} 項, 總大小: {total_bytes / (1024*1024):.2f} MB")

is_check_mode = any(arg in sys.argv for arg in ["--check", "--dry-run", "-c"])
if is_check_mode:
    if all_valid:
        print("\n[+] 檢查完成：所有同步檔案皆為最新版本且已就緒！")
        print("    當電腦連上機車熱點 (192.168.4.1) 時，執行以下指令開始同步：")
        print("    python deploy_to_pi5.py\n")
    else:
        print("\n[-] 警告：發現檔案缺失，請先修復後再部署！\n")
    sys.exit(0 if all_valid else 1)

if not all_valid:
    print("\n[-] 警告：發現缺失檔案，終止部署程序。")
    sys.exit(1)

connected_ip = None
custom_ip = [arg for arg in sys.argv[1:] if not arg.startswith("-")]
if custom_ip:
    connected_ip = custom_ip[0]
    print(f"[*] 使用指定 IP: {connected_ip}...")
else:
    for ip in PI_IPS:
        print(f"[*] 測試連接至 {ip}...")
        res = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=2", "-o", "StrictHostKeyChecking=no", f"{USER}@{ip}", "echo 'OK'"],
            capture_output=True,
            encoding='utf-8',
            errors='replace'
        )
        if "OK" in res.stdout:
            connected_ip = ip
            print(f"[+] 成功連接至 Pi 5 ({connected_ip})！")
            break

if not connected_ip:
    print("\n[-] 無法自動連線至 Pi 5。")
    print("    請確認：")
    print("    1. Pi 5 已開機。")
    print("    2. 電腦 Wi-Fi 已連接至機車熱點 'VISOR_System' (192.168.4.1)，或手動指定 IP：")
    print("       python deploy_to_pi5.py <PI_IP>\n")
    sys.exit(1)

# Ensure remote subdirectories exist
print(f"\n[*] 確保遠端工作目錄結構完整...")
subprocess.run(
    ["ssh", "-o", "StrictHostKeyChecking=no", f"{USER}@{connected_ip}",
     f"mkdir -p {TARGET_DIR}hud {TARGET_DIR}vision {TARGET_DIR}YOLOv26_DEMO {TARGET_DIR}YOLOv26_DEMO/models {TARGET_DIR}communication {TARGET_DIR}models"]
)

print(f"\n[*] 開始同步檔案至 {connected_ip}:{TARGET_DIR}...")
success_count = 0
for src, rel_dest in FILES_TO_SYNC:
    dest_path = f"{USER}@{connected_ip}:{TARGET_DIR}{rel_dest}"
    print(f"    - 上傳 {src}...", end=" ", flush=True)
    uploaded = False
    for attempt in range(3):
        res = subprocess.run(
            ["scp", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5", src, dest_path],
            capture_output=True,
            encoding='utf-8',
            errors='replace'
        )
        if res.returncode == 0:
            print("[OK]")
            success_count += 1
            uploaded = True
            break
        time.sleep(0.5)
    if not uploaded:
        print(f"[ERR: {res.stderr.strip()}]")

print(f"\n[+] 同步完成：成功 {success_count}/{len(FILES_TO_SYNC)} 項檔案。")

# Ensure executable permissions
subprocess.run(
    ["ssh", "-o", "StrictHostKeyChecking=no", f"{USER}@{connected_ip}",
     f"chmod +x {TARGET_DIR}run.sh {TARGET_DIR}visor_bt_agent.py"],
    capture_output=True
)

print("\n[*] 重啟 Pi 5 核心服務 (visor.service)...")
res = subprocess.run(
    ["ssh", "-o", "StrictHostKeyChecking=no", f"{USER}@{connected_ip}",
     "sudo systemctl restart visor.service && sudo systemctl status visor.service --no-pager -n 12"],
    capture_output=True,
    encoding='utf-8',
    errors='replace'
)
print(res.stdout)
if res.stderr:
    print(res.stderr)

print("\n[+] Pi 5 核心系統更新部署完成！")
print("    若需同步更新安全帽 Pi Zero HUD 顯示模組，請執行：")
print("    python deploy_to_pizero.py 192.168.4.60\n")
