import cv2
import time

print("測試 libcamerify 標準 V4L2 讀取...")

print("設定 IMX219 (對應 /dev/video0)")
cap0 = cv2.VideoCapture(0, cv2.CAP_V4L2)
cap0.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap0.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

print("設定 OV5647 (對應 /dev/video1 或 /dev/video2)")
# 有時第二個鏡頭會被指派到 index 1 或 2，我們試著讀取它
cap1 = cv2.VideoCapture(2, cv2.CAP_V4L2) 
if not cap1.isOpened():
    cap1 = cv2.VideoCapture(1, cv2.CAP_V4L2)
    cap1.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap1.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

time.sleep(1) # 給鏡頭一點時間初始化

if cap0.isOpened():
    ret0, frame0 = cap0.read()
    if ret0:
        print("[成功] 成功抓取 IMX219 的第一張影格！解析度:", frame0.shape)
    else:
        print("[失敗] IMX219 已開啟但抓不到影格。")
else:
    print("[失敗] 無法開啟 IMX219 (Sensor 0)")

if cap1.isOpened():
    ret1, frame1 = cap1.read()
    if ret1:
        print("[成功] 成功抓取 OV5647 的第一張影格！解析度:", frame1.shape)
    else:
        print("[失敗] OV5647 已開啟但抓不到影格。")
else:
    print("[失敗] 無法開啟 OV5647 (Sensor 1)")

cap0.release()
cap1.release()
