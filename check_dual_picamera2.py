import cv2
import time
from picamera2 import Picamera2

print("測試 Picamera2 官方原生 API 讀取...")

try:
    print("啟動 IMX219 (Camera 0)...")
    picam0 = Picamera2(camera=0)
    config0 = picam0.create_preview_configuration(main={"size": (640, 480), "format": "RGB888"})
    picam0.configure(config0)
    picam0.start()
    time.sleep(1)
    frame0 = picam0.capture_array()
    # Picamera2 輸出手為 RGB，若要給 OpenCV 顯示或標準使用可能需轉 BGR
    # frame0_bgr = cv2.cvtColor(frame0, cv2.COLOR_RGB2BGR)
    print("[成功] 成功抓取 IMX219 的第一張影格！解析度:", frame0.shape)
    picam0.stop()
except Exception as e:
    print("[失敗] IMX219 (Sensor 0):", e)

try:
    print("啟動 OV5647 (Camera 1)...")
    picam1 = Picamera2(camera=1)
    config1 = picam1.create_preview_configuration(main={"size": (640, 480), "format": "RGB888"})
    picam1.configure(config1)
    picam1.start()
    time.sleep(1)
    frame1 = picam1.capture_array()
    print("[成功] 成功抓取 OV5647 的第一張影格！解析度:", frame1.shape)
    picam1.stop()
except Exception as e:
    print("[失敗] OV5647 (Sensor 1):", e)

print("測試完畢！")
