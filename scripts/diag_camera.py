#!/usr/bin/env python3
"""
V.I.S.O.R. AI 診斷工具
拍一張照片 → 跑 YOLOv8 → 印出偵測結果 → 存檔標框圖片
"""
import cv2
import time
import subprocess
import sys
import os

def test_camera(cam_idx=0):
    port = 8000 + cam_idx
    tx_url = f"udp://127.0.0.1:{port}"
    rx_url = f"udp://127.0.0.1:{port}?overrun_nonfatal=1&fifo_size=50000000"

    print(f"\n{'='*50}")
    print(f"  測試鏡頭 {cam_idx}")
    print(f"{'='*50}")

    # 啟動硬體串流
    cmd = [
        "rpicam-vid", "-t", "0", "--camera", str(cam_idx),
        "--width", "640", "--height", "480", "--framerate", "30",
        "--codec", "mjpeg", "--hflip", "--vflip",
        "--awb", "auto", "--metering", "matrix",
        "--tuning-file", "/usr/share/libcamera/ipa/rpi/pisp/imx219.json",
        "-o", tx_url
    ]
    
    print(f"[1] 啟動 rpicam-vid 串流...")
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(3.0)
    
    if proc.poll() is not None:
        print(f"[ERROR] rpicam-vid 啟動失敗！嘗試 V4L2 模式...")
        cap = cv2.VideoCapture(cam_idx, cv2.CAP_V4L2)
    else:
        print(f"[OK] 硬體串流啟動成功")
        cap = cv2.VideoCapture(rx_url, cv2.CAP_FFMPEG)

    # 讀取幾幀讓相機穩定
    print(f"[2] 等待相機穩定...")
    for i in range(10):
        ret, frame = cap.read()
        time.sleep(0.1)

    ret, frame = cap.read()
    cap.release()
    proc.terminate()
    proc.wait()

    if not ret or frame is None:
        print(f"[FAIL] 鏡頭 {cam_idx} 無法讀取畫面！")
        return None
    
    print(f"[OK] 成功擷取畫面: {frame.shape[1]}x{frame.shape[0]}")
    return frame


def run_detection(frame, cam_label):
    from ultralytics import YOLO

    print(f"\n[3] 載入 YOLOv8n 模型...")
    model = YOLO("yolov8n.pt")
    
    # CLAHE 前處理（與 main_controller 相同）
    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    cl = clahe.apply(l)
    limg = cv2.merge((cl, a, b))
    proc_frame = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)

    print(f"[4] 執行 AI 推論中...")
    results = model(proc_frame, verbose=False)
    
    detections = []
    for r in results:
        for box in r.boxes:
            cls_id = int(box.cls[0])
            cls_name = model.names[cls_id]
            conf = float(box.conf[0])
            x1, y1, x2, y2 = [int(v) for v in box.xyxy[0]]
            w = x2 - x1
            h = y2 - y1
            cx = (x1 + x2) // 2
            cy = (y1 + y2) // 2
            detections.append({
                "class": cls_name, "conf": conf,
                "bbox": (x1, y1, x2, y2), "center": (cx, cy),
                "size": (w, h)
            })
    
    # 印出結果
    print(f"\n{'='*50}")
    print(f"  偵測結果 ({cam_label}): 共 {len(detections)} 個物件")
    print(f"{'='*50}")
    
    if not detections:
        print("  ⚠️  沒有偵測到任何物件！")
        print("  可能原因：")
        print("  - 鏡頭對焦不清晰（請手動轉動鏡頭外圈）")
        print("  - 測試影片畫面太小或太遠")
        print("  - 色差太嚴重導致特徵丟失")
    else:
        for i, d in enumerate(detections):
            print(f"  [{i+1}] {d['class']:12s} | 信心度: {d['conf']:.2f} | "
                  f"位置: ({d['center'][0]:3d},{d['center'][1]:3d}) | "
                  f"大小: {d['size'][0]:3d}x{d['size'][1]:3d}px | "
                  f"框: {d['bbox']}")
            
            # 在原圖上畫框
            x1, y1, x2, y2 = d['bbox']
            color = (0, 0, 255) if d['conf'] > 0.5 else (0, 255, 255)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            label = f"{d['class']} {d['conf']:.2f}"
            cv2.putText(frame, label, (x1, y1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
    
    # 存檔
    out_path = f"/home/pi5/diag_{cam_label}.jpg"
    cv2.imwrite(out_path, frame)
    print(f"\n[5] 標框結果已存檔: {out_path}")
    
    return detections


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)) or "/home/pi5/motorcycle_assist")
    
    # 測試哪個鏡頭（預設測試全部）
    cameras = [0, 1]
    if len(sys.argv) > 1:
        cameras = [int(sys.argv[1])]
    
    for cam in cameras:
        label = "front" if cam == 0 else "rear"
        frame = test_camera(cam)
        if frame is not None:
            run_detection(frame, label)
        
        # 清理
        subprocess.run(["killall", "rpicam-vid"], 
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1)
    
    print(f"\n{'='*50}")
    print(f"  診斷完成！")
    print(f"  如果有標框，可以用以下指令把圖片拉回 Windows 查看：")
    print(f"  scp pi5@pi5:~/diag_front.jpg .")
    print(f"  scp pi5@pi5:~/diag_rear.jpg .")
    print(f"{'='*50}")
