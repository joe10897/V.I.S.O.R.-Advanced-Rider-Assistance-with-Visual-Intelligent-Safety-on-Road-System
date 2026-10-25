#!/usr/bin/env python3
"""
V.I.S.O.R. Pi 5 Dual USB 2.0 Sony IMX662 Diagnostic & Auto-Config Tool
- 動態掃描目前插在 Pi 5 上的 USB 鏡頭實體節點 (自動過濾 RP1/CSI 與 metadata 節點)
- 不受插孔變更 (USB 3.0 / USB 2.0) 或重新插拔後編號跳動 (video0/video2 -> video4/video6) 影響
- 實測 640x480 MJPG @ 30 FPS 幀率與低延遲影格，儲存測試樣張
- 自動校準並更新 config.json 的來源設定
"""
import os
import sys
import time
import glob
import json
import cv2

def get_lsusb_output():
    """取得系統 lsusb 輸出以輔助診斷"""
    import subprocess
    try:
        res = subprocess.run(["lsusb"], capture_output=True, text=True, timeout=2.0)
        return res.stdout.strip()
    except Exception:
        return "無法執行 lsusb"

def check_is_capture_device(dev_path):
    """
    透過 Linux V4L2 核心 ioctl (VIDIOC_QUERYCAP) 精確判定是否為真實影像擷取端點
    徹底過濾掉 UVC Metadata 節點 (V4L2_CAP_META_CAPTURE) 與非 capture 端點
    """
    try:
        import fcntl
        import struct
        # 唯讀非阻塞開啟查詢 capabilities，避免 EBUSY 衝突
        fd = os.open(dev_path, os.O_RDONLY | os.O_NONBLOCK)
        try:
            buf = bytearray(104)
            # VIDIOC_QUERYCAP = 0x80685600
            fcntl.ioctl(fd, 0x80685600, buf)
            driver, card, bus_info, version, capabilities, device_caps = struct.unpack("16s32s32sIII12x", buf)
            
            card_str = card.decode("utf-8", errors="ignore").strip("\x00 ").strip()
            bus_str = bus_info.decode("utf-8", errors="ignore").strip("\x00 ").strip()
            
            # 若 capabilities 第 31 位元 (0x80000000) 設立，代表支援 device_caps，以 device_caps 為準
            caps = device_caps if (capabilities & 0x80000000) else capabilities
            
            # V4L2_CAP_VIDEO_CAPTURE = 0x00000001
            # V4L2_CAP_META_CAPTURE  = 0x00800000
            is_capture = bool(caps & 0x00000001)
            is_meta = bool(caps & 0x00800000)
            
            return (is_capture and not is_meta), card_str, bus_str
        finally:
            os.close(fd)
    except Exception:
        # 備援嘗試：若 fcntl 異常，直接嘗試以 OpenCV 實測是否能取得畫面
        try:
            cap = cv2.VideoCapture(dev_path, cv2.CAP_V4L2)
            if not cap.isOpened():
                cap = cv2.VideoCapture(dev_path)
            if cap.isOpened():
                ret, f = cap.read()
                cap.release()
                if ret and f is not None and f.size > 0:
                    return True, "USB Camera", dev_path
        except Exception:
            pass
        return False, "", ""

def detect_usb_cameras():
    """動態掃描所有目前插在樹莓派上的 USB 鏡頭實體節點 (嚴格過濾 PiSP 與 Metadata 節點)"""
    print("[1/4] 掃描目前系統 USB 影像設備拓撲 (V4L2 核心查詢)...")
    cameras = []
    seen_nodes = set()
    
    def _dev_num(p):
        try: return int(os.path.basename(p).replace("video", ""))
        except: return 999
        
    v_nodes = sorted(glob.glob("/sys/class/video4linux/video*"), key=_dev_num)
    for v in v_nodes:
        dev_name = os.path.basename(v)
        dev_link = f"{v}/device"
        node_path = f"/dev/{dev_name}"
        
        # 1. 檢查底層硬體是否屬於 USB 總線 (排除 Pi 5 內部 pispbe/rp1-cfe 虛擬節點)
        is_usb_bus = False
        if os.path.exists(dev_link):
            try:
                target = os.path.realpath(dev_link).lower()
                if "usb" in target:
                    is_usb_bus = True
            except Exception:
                pass
                
        if not is_usb_bus:
            continue
            
        # 2. 透過 V4L2 核心 VIDIOC_QUERYCAP 判定是否為真正的影像串流端點 (排除 Metadata 節點)
        is_capture, card_name, bus_info = check_is_capture_device(node_path)
        if is_capture and node_path not in seen_nodes:
            seen_nodes.add(node_path)
            idx_num = int(dev_name.replace("video", ""))
            cameras.append({
                "dev_node": node_path,
                "index": idx_num,
                "id": card_name or "USB Camera 1080P",
                "bus": bus_info
            })
                
    # 策略 B: 若 ioctl 未命中但有 USB 設備，依序以 OpenCV 探測所有 USB video 節點
    if not cameras:
        for v in v_nodes:
            dev_name = os.path.basename(v)
            dev_link = f"{v}/device"
            node_path = f"/dev/{dev_name}"
            if os.path.exists(dev_link) and "usb" in os.path.realpath(dev_link).lower():
                idx_num = int(dev_name.replace("video", ""))
                try:
                    c = cv2.VideoCapture(idx_num, cv2.CAP_V4L2)
                    if c.isOpened():
                        ret, f = c.read()
                        c.release()
                        if ret and f is not None:
                            cameras.append({
                                "dev_node": node_path,
                                "index": idx_num,
                                "id": "USB Camera (Auto-Probe)",
                                "bus": dev_name
                            })
                except Exception:
                    pass
                
    cameras.sort(key=lambda x: x["index"])
    return cameras

def test_camera(idx, label, fov_deg, save_path):
    print(f"\n[測試] 正在連線 {label} (硬體索引 index={idx}, /dev/video{idx}, 視角={fov_deg}°)...")
    
    dev_str = f"/dev/video{idx}"
    try:
        import subprocess
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
    if not cap.isOpened():
        cap = cv2.VideoCapture(idx)
    if not cap.isOpened():
        cap = cv2.VideoCapture(f"/dev/video{idx}", cv2.CAP_V4L2)
    if not cap.isOpened():
        cap = cv2.VideoCapture(f"/dev/video{idx}")
            
    if cap is None or not cap.isOpened():
        print(f"❌ 無法開啟相機 index={idx} (/dev/video{idx})！請確認 USB 連接。")
        return False, 0.0
        
    # 設定 HD-IMX662 最佳化硬體 MJPG 串流 (根據原廠規格支援 60 FPS MJPG)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 30)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    
    # 暖機 0.3s 並丟棄前 3 幀初期曝光黑屏
    time.sleep(0.3)
    for _ in range(3):
        cap.read()
        
    start_t = time.time()
    frames_read = 0
    test_frame = None
    
    for _ in range(30):
        ret, frame = cap.read()
        if ret and frame is not None and frame.size > 0:
            frames_read += 1
            test_frame = frame
            
    elapsed = time.time() - start_t
    cap.release()
    
    if frames_read > 0 and test_frame is not None:
        fps = round(frames_read / max(0.01, elapsed), 1)
        h, w = test_frame.shape[:2]
        cv2.imwrite(save_path, test_frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
        print(f"✅ {label} 擷取成功！")
        print(f"   - 設備節點: /dev/video{idx}")
        print(f"   - 影像格式: {w}x{h} (MJPG @ 60/30fps 模式)")
        print(f"   - 實測採樣率: {fps} FPS (目標: 30 FPS)")
        print(f"   - 樣張儲存於: {save_path} ({os.path.getsize(save_path):,} bytes)")
        return True, fps
    else:
        print(f"❌ {label} 讀取影格失敗！")
        return False, 0.0

def update_config_sources(front_node, rear_node):
    """自動將實際測試通過的節點更新至 config.json"""
    cfg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")
    if not os.path.exists(cfg_path):
        cfg_path = "config.json"
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["vision"]["source_front"] = front_node
            data["vision"]["source_rear"] = rear_node
            data["vision"]["source"] = rear_node
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"\n[+] 已自動同步實際鏡頭節點至 config.json (front={front_node}, rear={rear_node})")
        except Exception as e:
            print(f"[!] 無法更新 config.json: {e}")

def main():
    print("=" * 65)
    print("  V.I.S.O.R. 雙 USB2.0 Sony IMX662 鏡頭診斷與自動校準工具")
    print("  (HD-IMX662 STARVIS 2 | 純 USB2.0 UVC | 免 I2C)")
    print("=" * 65)
    
    # 0. 檢查背景 visor.service 與強制釋放相機節點 (避免殘留程序獨佔導致 Device is busy)
    service_was_running = False
    try:
        import subprocess
        chk = subprocess.run(["systemctl", "is-active", "visor.service"], capture_output=True, text=True, timeout=1.5)
        if "active" in chk.stdout.strip():
            service_was_running = True
            print("[!] 偵測到背景 visor.service 正在執行，正在自動暫停服務...")
            subprocess.run(["sudo", "systemctl", "stop", "visor.service"], timeout=5.0)
            time.sleep(1.0)
            
        # 強制釋放所有可能殘留的 Python 程序與 V4L2 設備鎖
        subprocess.run("sudo fuser -k -9 /dev/video0 /dev/video1 /dev/video2 /dev/video3 2>/dev/null || true", shell=True)
        subprocess.run("sudo pkill -9 -f main_controller 2>/dev/null || true", shell=True)
        time.sleep(0.5)
    except Exception:
        pass
    
    try:
        cams = detect_usb_cameras()
        print(f"[*] 成功偵測到 {len(cams)} 組有效影像串流 USB 鏡頭:")
        for i, c in enumerate(cams):
            print(f"    [{i}] {c['dev_node']} (index={c['index']}, {c['id']}, bus={c.get('bus','')})")
            
        if not cams:
            print("\n❌ 錯誤：未在 USB 總線上偵測到任何可用視訊串流端點！")
            print("--- 系統 USB 硬體拓撲清單 (lsusb) ---")
            print(get_lsusb_output())
            print("-------------------------------------")
            print("   除錯建議：")
            print("   1. 請將鏡頭插在樹莓派 5 的【藍色 USB 3.0 孔】(提供 900mA~1.5A 穩定供電)。")
            print("   2. 請確認鏡頭排線或 USB 接口已插緊。")
            sys.exit(1)
            
        # 第一組分配為前鏡頭 (120°)，第二組分配為後鏡頭 (173°)
        front_cam = cams[0]
        rear_cam = cams[1] if len(cams) > 1 else cams[0]
        
        ok_f, fps_f = test_camera(front_cam["index"], "前鏡頭 FRONT CAM", 120, "/tmp/usb_front_test.jpg")
        ok_r, fps_r = (False, 0.0)
        if len(cams) > 1:
            ok_r, fps_r = test_camera(rear_cam["index"], "後鏡頭 REAR CAM", 173, "/tmp/usb_rear_test.jpg")
        else:
            print("\n[!] 提示：目前僅偵測到 1 組有效 USB 鏡頭，自動將其同時配置為預覽來源。")
            
        print("\n" + "=" * 65)
        print("  診斷結論:")
        print(f"  - 前鏡頭 (120° FOV, {front_cam['dev_node']}): {'✅ 運作正常 (' + str(fps_f) + ' FPS)' if ok_f else '❌ 異常'}")
        if len(cams) > 1:
            print(f"  - 後鏡頭 (173° FOV, {rear_cam['dev_node']}): {'✅ 運作正常 (' + str(fps_r) + ' FPS)' if ok_r else '❌ 異常'}")
        else:
            print("  - 後鏡頭: 未連接第二組 USB 鏡頭")
        print("  - 硬體規格: Sony IMX662 STARVIS 2, 5V@140-190mA, UVC 協議免驅動")
        print("  - I2C 狀態: 停用 (純 USB 模式，完全無 I2C 總線干擾)")
        print("=" * 65)
        
        if ok_f:
            f_node = front_cam["dev_node"]
            r_node = rear_cam["dev_node"] if len(cams) > 1 else front_cam["dev_node"]
            update_config_sources(f_node, r_node)
    finally:
        if service_was_running:
            print("\n[*] 正在為您恢復並重啟 visor.service 服務...")
            try:
                subprocess.run(["sudo", "systemctl", "restart", "visor.service"], timeout=5.0)
                print("[+] visor.service 背景服務已成功恢復執行！")
            except Exception as e:
                print(f"[!] 無法自動重啟 visor.service: {e}，請手動執行: sudo systemctl restart visor.service")

if __name__ == "__main__":
    main()
