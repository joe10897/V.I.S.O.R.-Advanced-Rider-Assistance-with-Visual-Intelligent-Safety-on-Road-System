import cv2
import subprocess
import time

print("測試 rpicam-vid + MJPEG 本地串流架構...")

# 啟動 Camera 0 的硬體加速影片流 (IMX219)
print("啟動 IMX219 串流至 udp://127.0.0.1:8000 ...")
proc0 = subprocess.Popen([
    "rpicam-vid", "-t", "0", "--camera", "0", 
    "--width", "640", "--height", "480", "--framerate", "30",
    "--codec", "mjpeg", "-o", "udp://127.0.0.1:8000"
], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# 啟動 Camera 1 的硬體加速影片流 (OV5647)
print("啟動 OV5647 串流至 udp://127.0.0.1:8001 ...")
proc1 = subprocess.Popen([
    "rpicam-vid", "-t", "0", "--camera", "1", 
    "--width", "640", "--height", "480", "--framerate", "30",
    "--codec", "mjpeg", "-o", "udp://127.0.0.1:8001"
], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# 給硬體 2 秒鐘初始化與串流
time.sleep(2)

print("嘗試用 OpenCV 讀取 IMX219...")
cap0 = cv2.VideoCapture("udp://127.0.0.1:8000", cv2.CAP_FFMPEG)
if cap0.isOpened():
    ret0, frame0 = cap0.read()
    if ret0:
        print("[成功] 成功抓取 IMX219 的第一張影格！解析度:", frame0.shape)
    else:
        print("[失敗] IMX219 已開啟但沒收到 UDP 資料。")
else:
    print("[失敗] 無法開啟 IMX219 (Sensor 0) 串流。")

print("嘗試用 OpenCV 讀取 OV5647...")
cap1 = cv2.VideoCapture("udp://127.0.0.1:8001", cv2.CAP_FFMPEG)
if cap1.isOpened():
    ret1, frame1 = cap1.read()
    if ret1:
        print("[成功] 成功抓取 OV5647 的第一張影格！解析度:", frame1.shape)
    else:
        print("[失敗] OV5647 已開啟但沒收到 UDP 資料。")
else:
    print("[失敗] 無法開啟 OV5647 (Sensor 1) 串流。")

# 清理資源與關閉背景程序
cap0.release()
cap1.release()
proc0.terminate()
proc1.terminate()
proc0.wait()
proc1.wait()
print("測試完畢！背景串流已關閉。")
