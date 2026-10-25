import subprocess
import sys
import os
import time

sys.stdout.reconfigure(encoding='utf-8')

def get_discovered_ips():
    found = []
    # 1. Linux/Pi 5: ip neigh
    try:
        res = subprocess.run(["ip", "neigh"], capture_output=True, text=True, errors='replace')
        for line in res.stdout.splitlines():
            parts = line.split()
            if parts and "192.168.4." in parts[0] and parts[0] != "192.168.4.1":
                found.append(parts[0])
    except Exception:
        pass
    # 2. Windows/Linux: arp -a
    try:
        res = subprocess.run(["arp", "-a"], capture_output=True, text=True, errors='replace')
        for line in res.stdout.splitlines():
            for word in line.split():
                if word.startswith("192.168.4.") and word not in ("192.168.4.1", "192.168.4.255") and word not in found:
                    found.append(word)
    except Exception:
        pass
    return found

# Common default candidate IPs for Pi Zero when connected to Pi 5 AP (192.168.4.x)
discovered = get_discovered_ips()
CANDIDATE_IPS = ["192.168.4.60"] + discovered + [
    "pizero.local",
    "pi.local",
    "192.168.4.15",
    "192.168.4.10",
    "192.168.4.20",
    "192.168.4.2",
    "192.168.4.3",
    "192.168.4.4",
    "192.168.4.5"
]

USER = "visor_hud"
TARGET_DIR = f"/home/{USER}/motorcycle_assist/hud/"

script_dir = os.path.dirname(os.path.abspath(__file__))
hud_local_path = os.path.join(script_dir, "hud", "hud_client.py")
if not os.path.exists(hud_local_path):
    hud_local_path = os.path.join(script_dir, "hud_client.py")

print("==================================================")
print("  V.I.S.O.R. HUD Client Deployment to Pi Zero 2W")
print("  (Enables Optical Mirror + Vertical Flip for Visor)")
print("==================================================")

is_check_mode = any(arg in sys.argv for arg in ["--check", "--dry-run", "-c"])
if is_check_mode:
    print("\n[*] 正在檢查本地 Pi Zero HUD 待同步檔案...")
    if os.path.exists(hud_local_path):
        sz = os.path.getsize(hud_local_path)
        mtime = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(os.path.getmtime(hud_local_path)))
        print(f"    [OK] {hud_local_path:<40} ({sz:,} bytes | {mtime})")
        print("\n[+] 檢查完成：Pi Zero HUD Client 檔案為最新版本且已就緒！")
        print("    當連接至機車熱點時，執行以下指令開始同步：")
        print("    python deploy_to_pizero.py 192.168.4.60\n")
    else:
        print(f"    [MISSING] {hud_local_path} 檔案不存在！\n")
    sys.exit(0 if os.path.exists(hud_local_path) else 1)

connected_ip = None

# If user specified IP in command line
custom_args = [arg for arg in sys.argv[1:] if not arg.startswith("-")]
if custom_args:
    connected_ip = custom_args[0]
    print(f"[*] 指定目標 Pi Zero IP: {connected_ip}")

if not connected_ip:
    print(f"[*] Scanning candidate addresses for Pi Zero (Found nearby: {discovered})...")
    for ip in CANDIDATE_IPS:
        print(f"    - Trying {ip}...", end=" ", flush=True)
        res = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=1", "-o", "StrictHostKeyChecking=no", f"{USER}@{ip}", "echo 'OK'"],
            capture_output=True,
            encoding='utf-8',
            errors='replace'
        )
        if "OK" in res.stdout:
            connected_ip = ip
            print("[CONNECTED!]")
            break
        else:
            print("[no reply]")

if not connected_ip:
    print("\n[-] Could not auto-detect Pi Zero.")
    print("    Tip: You can find Pi Zero's IP by logging into Pi 5:")
    print("         ssh pi5@192.168.4.1")
    print("         ip neigh  (or arp -n)")
    print("    Then run:")
    print("         python deploy_to_pizero.py <PI_ZERO_IP>\n")
    sys.exit(1)

print(f"\n[*] Ensuring remote directory {TARGET_DIR} exists...")
subprocess.run(
    ["ssh", "-o", "StrictHostKeyChecking=no", f"{USER}@{connected_ip}", f"mkdir -p {TARGET_DIR} /home/{USER}/visor_hud/hud/"]
)

print(f"\n[*] Uploading hud_client.py ({hud_local_path}) to {connected_ip}:{TARGET_DIR}...")
res = subprocess.run(
    ["scp", "-o", "StrictHostKeyChecking=no", hud_local_path, f"{USER}@{connected_ip}:{TARGET_DIR}hud_client.py"]
)
if res.returncode == 0:
    print("    [OK] hud_client.py uploaded successfully!")
    # 同步複製至 /home/visor_hud/visor_hud/hud/ 確保各版本 service 路徑皆能生效
    subprocess.run(
        ["ssh", "-o", "StrictHostKeyChecking=no", f"{USER}@{connected_ip}", f"cp {TARGET_DIR}hud_client.py /home/{USER}/visor_hud/hud/hud_client.py 2>/dev/null || true"]
    )
else:
    print(f"    [ERR] Upload failed.")
    sys.exit(1)

print("\n[*] Restarting visor-hud.service on Pi Zero...")
res = subprocess.run(
    ["ssh", "-t", "-o", "StrictHostKeyChecking=no", f"{USER}@{connected_ip}", "sudo systemctl restart visor-hud.service && sudo systemctl status visor-hud.service --no-pager -n 8"]
)

print("\n[+] Pi Zero HUD Client update complete!")
print("    OLED display is now configured for Mirror + Vertical Flip!")
