import cv2

def gstreamer_pipeline(sensor_id=0, capture_width=640, capture_height=480, framerate=30):
    # 更穩定的 Pi 5 libcamerasrc 管道，強制轉為 BGR 供 OpenCV 讀取
    return (
        f"libcamerasrc camera-name={sensor_id} ! "
        f"video/x-raw, width={capture_width}, height={capture_height}, framerate={framerate}/1 ! "
        "videoconvert ! "
        "video/x-raw, format=BGR ! appsink drop=true sync=false"
    )

print("測試 GStreamer 管道 2.0 ...")

print("嘗試讀取 IMX219 (通常對應 sensor 0) ...")
cap0 = cv2.VideoCapture(gstreamer_pipeline(sensor_id=0), cv2.CAP_GSTREAMER)

print("嘗試讀取 OV5647 (通常對應 sensor 1) ...")
cap1 = cv2.VideoCapture(gstreamer_pipeline(sensor_id=1), cv2.CAP_GSTREAMER)

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
