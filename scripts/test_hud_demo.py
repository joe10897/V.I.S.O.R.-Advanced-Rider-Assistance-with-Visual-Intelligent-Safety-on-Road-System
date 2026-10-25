#!/usr/bin/env python3
# =============================================================
#  V.I.S.O.R. OLED HUD 全情境動態測試腳本
#  用途：直接向 HUD 發送即時情境數據，動態驗證時速、傾角、測速照相、
#        左右盲點雙箭頭、前後方防撞分級警示與全屏反白頻閃功能。
# =============================================================

import socket
import json
import time
import sys
import argparse

def create_payload(speed=0, tilt=0, warning=None, cam_alert=None, hud_config=None, cpu=18, temp=42.5):
    if hud_config is None:
        hud_config = {
            "speed": True, "camera": True, "nav": True, "time": True, "brightness": 200,
            "mirror": True, "flip_v": True
        }
    
    app_data = {
        "speed": speed,
        "tilt": tilt,
    }
    if cam_alert:
        app_data["cameraAlert"] = cam_alert

    return {
        "timestamp": time.time(),
        "speed": speed,
        "tilt": tilt,
        "warning": warning,
        "radar_targets": [],
        "ai_results": [],
        "system": {
            "pi5_status": "online",
            "hud_status": "online",
            "cpu": cpu,
            "mem": 35.0,
            "temp": temp
        },
        "recording": {
            "is_recording": True,
            "duration": 120
        },
        "hud_config": hud_config,
        "app_data": app_data,
        "alert": 1 if warning and warning.get("level") == "danger" else 0
    }

def run_test(target_ip="127.0.0.1", port=5005, loop=False):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    
    print("=" * 65)
    print("   🏍️  V.I.S.O.R. OLED HUD 動態情境自動化測試啟動")
    print(f"   目標位址: {target_ip}:{port}")
    print("=" * 65)
    
    def send(payload, duration=1.0, hz=20):
        interval = 1.0 / hz
        steps = int(duration * hz)
        for _ in range(steps):
            payload["timestamp"] = time.time()
            msg = json.dumps(payload).encode('utf-8')
            try:
                sock.sendto(msg, (target_ip, port))
            except Exception as e:
                pass
            time.sleep(interval)

    while True:
        # -------------------------------------------------------------
        # 情境 1: 正常加速巡航 (0 -> 98 km/h，左右自然過彎傾角)
        # -------------------------------------------------------------
        print("\n[SCENARIO 1] 🟢 正常騎乘巡航：車速平滑加速 (0 -> 98 km/h)，壓車過彎傾角")
        for spd in range(0, 100, 4):
            tilt = int(18 * (1 if spd % 30 < 15 else -1) * (spd / 100.0))
            payload = create_payload(speed=spd, tilt=tilt)
            send(payload, duration=0.1, hz=20)
            sys.stdout.write(f"\r  >> 目前時速: {spd:3d} km/h | 車身傾角: {tilt:+3d}° | 狀態: 巡航正常")
            sys.stdout.flush()
        print(" [完成]")

        # -------------------------------------------------------------
        # 情境 2: 前方測速照相預警 (CAM 50 | 倒數 350m -> 40m)
        # -------------------------------------------------------------
        print("\n[SCENARIO 2] 📷 測速照相提醒：固定測速 50km/h，距離動態逼近倒數")
        for dist in range(350, 30, -25):
            cam_alert = {"limit": 50, "distance": dist}
            payload = create_payload(speed=68, tilt=2, cam_alert=cam_alert)
            send(payload, duration=0.2, hz=20)
            sys.stdout.write(f"\r  >> 測速相機限速: 50 km/h | 距離: {dist:3d}m [閃爍提醒中]")
            sys.stdout.flush()
        print(" [完成]")

        # -------------------------------------------------------------
        # 情境 3: 左側盲點注意警示 (Left BSD - 螢幕左緣 ◀◀ 雙箭頭閃爍)
        # -------------------------------------------------------------
        print("\n[SCENARIO 3] 🟡 左側盲點警示 (二級注意)：左邊緣 ◀◀ 雙箭頭高亮閃爍")
        for dist in [18.5, 15.2, 12.0, 9.5, 8.0]:
            warn = {
                "direction": "left",
                "level": "warning",
                "message": "左側車輛逼近",
                "dist": dist,
                "class_name": "CAR",
                "ttc": 2.2
            }
            payload = create_payload(speed=75, tilt=-5, warning=warn)
            send(payload, duration=0.6, hz=20)
            sys.stdout.write(f"\r  >> 左側盲點車輛: {dist:.1f}m | 方位: LEFT ◀◀ | 橫幅: < LEFT BSD CAR")
            sys.stdout.flush()
        print(" [完成]")

        # -------------------------------------------------------------
        # 情境 4: 右側盲點注意警示 (Right BSD - 螢幕右緣 ▶▶ 雙箭頭閃爍)
        # -------------------------------------------------------------
        print("\n[SCENARIO 4] 🟡 右側盲點警示 (二級注意)：右邊緣 ▶▶ 雙箭頭高亮閃爍")
        for dist in [16.0, 13.5, 10.2, 7.8]:
            warn = {
                "direction": "right",
                "level": "warning",
                "message": "右側機車逼近",
                "dist": dist,
                "class_name": "SCOOTER",
                "ttc": 1.9
            }
            payload = create_payload(speed=62, tilt=4, warning=warn)
            send(payload, duration=0.6, hz=20)
            sys.stdout.write(f"\r  >> 右側盲點機車: {dist:.1f}m | 方位: RIGHT ▶▶ | 橫幅: > RIGHT BSD SCOOTER")
            sys.stdout.flush()
        print(" [完成]")

        # -------------------------------------------------------------
        # 情境 5: 前方防撞預警 (Front FCW - 距離 16m)
        # -------------------------------------------------------------
        print("\n[SCENARIO 5] 🟡 前方防撞警示 (二級注意)：前車減速提醒")
        warn = {
            "direction": "front",
            "level": "warning",
            "message": "前方公車減速",
            "dist": 14.5,
            "class_name": "BUS",
            "ttc": 1.8
        }
        payload = create_payload(speed=55, tilt=0, warning=warn)
        send(payload, duration=2.5, hz=20)
        print("  >> 前方公車 14.5m 提醒完成")

        # -------------------------------------------------------------
        # 情境 6: 致命碰撞一級危險 (Critical Collision - 全屏反白頻閃)
        # -------------------------------------------------------------
        print("\n[SCENARIO 6] 🔴 致命碰撞一級危險 (Danger)：後方極速逼近 (<4m / TTC 0.8s) 全屏反白頻閃！")
        for dist in [5.8, 4.5, 3.8, 3.2, 2.6]:
            warn = {
                "direction": "rear",
                "level": "danger",
                "message": "後方急速逼近",
                "dist": dist,
                "class_name": "CAR",
                "ttc": 0.8
            }
            payload = create_payload(speed=42, tilt=0, warning=warn)
            send(payload, duration=0.6, hz=25)
            sys.stdout.write(f"\r  >> 🚨 致命碰撞警報: 距離 {dist:.1f}m | 頻閃反白中！")
            sys.stdout.flush()
        print(" [完成]")

        # -------------------------------------------------------------
        # 情境 7: HUD 配置即時動態切換測試 (關閉時速、調整亮度)
        # -------------------------------------------------------------
        print("\n[SCENARIO 7] ⚙️ HUD 配置即時同步測試：動態關閉時速、開啟純導航與調光")
        cfg_custom = {"speed": False, "camera": True, "nav": True, "time": True, "brightness": 120}
        payload = create_payload(speed=85, tilt=10, hud_config=cfg_custom)
        send(payload, duration=2.0, hz=20)
        print("  >> 時速隱藏模式測試完成")

        cfg_restore = {"speed": True, "camera": True, "nav": True, "time": True, "brightness": 220}
        payload = create_payload(speed=50, tilt=0, hud_config=cfg_restore)
        send(payload, duration=1.5, hz=20)
        print("  >> 完整儀表恢復測試完成")

        print("\n" + "=" * 65)
        print("   ✅ 全情境 HUD 測試循環完成！")
        print("=" * 65)

        if not loop:
            break
        print("\n>> 3 秒後進入下一次自動循環 (Ctrl+C 可停止)...")
        time.sleep(3)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="V.I.S.O.R. OLED HUD Dynamic Test Suite")
    parser.add_argument("--ip", default="127.0.0.1", help="Target IP address (default: 127.0.0.1, or 192.168.4.60)")
    parser.add_argument("--port", type=int, default=5005, help="Target UDP port (default: 5005)")
    parser.add_argument("--loop", action="store_true", help="Continuously loop through all scenarios")
    args = parser.parse_args()
    
    try:
        run_test(target_ip=args.ip, port=args.port, loop=args.loop)
    except KeyboardInterrupt:
        print("\n\n[INFO] 測試已手動停止。")
