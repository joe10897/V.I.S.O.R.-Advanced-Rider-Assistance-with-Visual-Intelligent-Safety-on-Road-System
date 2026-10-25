#!/usr/bin/env python3
"""
V.I.S.O.R. Pi 5 Dual MIPI-CSI Camera Diagnostic Tool
Automatically terminates lingering camera processes and tests both cameras.
"""
import subprocess
import os
import sys
import time

def cleanup():
    """強制釋放所有相機硬體管線"""
    subprocess.run("pkill -9 -f rpicam 2>/dev/null; pkill -9 -f libcamera 2>/dev/null", shell=True)
    time.sleep(0.6)

def run_cmd(cmd):
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True)
        return res.stdout.strip()
    except Exception as e:
        return str(e)

print("=" * 60)
print("  V.I.S.O.R. Pi 5 雙 MIPI-CSI 鏡頭自動診斷工具 (含自動清理)")
print("=" * 60)

# 0. 自動清理舊程序
print("\n[步驟 0] 自動清理被佔用的相機管線與背景程序...")
cleanup()
print("✅ 相機硬體資源已強制重置與釋放！")

# 1. 偵測硬體鏡頭清單
print("\n[步驟 1] 掃描 Pi 5 上的 CSI 鏡頭硬體...")
list_output = run_cmd("rpicam-hello --list-cameras 2>/dev/null || libcamera-hello --list-cameras 2>/dev/null")
print("------------------------------------------------------------")
if list_output:
    print(list_output)
else:
    print("⚠️ 未檢測到 rpicam-hello 輸出，嘗試讀取 /dev/video* ...")
    v4l2_out = run_cmd("v4l2-ctl --list-devices 2>/dev/null")
    print(v4l2_out if v4l2_out else "無 v4l2-ctl 輸出")
print("------------------------------------------------------------")

# 2. 測試 Camera 0 (前鏡頭 - IMX219 120°)
print("\n[步驟 2] 測試 Camera 0 (前鏡頭)...")
cleanup()
cmd_cam0 = "rpicam-still -t 1200 --camera 0 -o /tmp/cam0_test.jpg --width 640 --height 480 --nopreview 2>&1"
out0 = run_cmd(cmd_cam0)
if os.path.exists("/tmp/cam0_test.jpg") and os.path.getsize("/tmp/cam0_test.jpg") > 1000:
    print(f"✅ Camera 0 (前鏡頭) 擷取成功！大小: {os.path.getsize('/tmp/cam0_test.jpg')} bytes -> /tmp/cam0_test.jpg")
else:
    print(f"❌ Camera 0 失敗: {out0}")

# 3. 測試 Camera 1 (後鏡頭 - OV5647 160°)
print("\n[步驟 3] 測試 Camera 1 (後鏡頭)...")
cleanup()
cmd_cam1 = "rpicam-still -t 1200 --camera 1 -o /tmp/cam1_test.jpg --width 640 --height 480 --nopreview 2>&1"
out1 = run_cmd(cmd_cam1)
if os.path.exists("/tmp/cam1_test.jpg") and os.path.getsize("/tmp/cam1_test.jpg") > 1000:
    print(f"✅ Camera 1 (後鏡頭) 擷取成功！大小: {os.path.getsize('/tmp/cam1_test.jpg')} bytes -> /tmp/cam1_test.jpg")
else:
    print(f"❌ Camera 1 失敗: {out1}")

cleanup()
print("\n" + "=" * 60)
print("  診斷完成！相機硬體已自動釋放，可隨時啟動 main_controller.py")
print("=" * 60)
