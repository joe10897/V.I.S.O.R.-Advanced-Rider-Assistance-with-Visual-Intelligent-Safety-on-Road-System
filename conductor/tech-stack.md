# Technology Stack: V.I.S.O.R.

## Hardware Components
- **Central Processing Unit (The Brain):** Raspberry Pi 5
    - **Vision Input (Target):** 
        - 前鏡頭：CSI 介面 IMX219 (120度) 高清攝影鏡頭
        - 後鏡頭：CSI 介面 IMX219 (160度) 高清攝影鏡頭
    - **Vision Input (Current Test):** USB Webcam (用於原型開發與邏輯測試)
    - **Sensors:** MPU-6050 (IMU), GPS 模組
- **Display Unit (The Eyes):** Raspberry Pi Zero 2 W
    - **Display:** SSD1306 OLED (128x64, I2C)
- **User Interface:** Android Smartphone

## Software & AI
- **Languages:** Python 3.10+ (Pi 5/Zero), JavaScript/React (Mobile)
- **AI Framework:** Ultralytics YOLOv8 (v8n)
    - **Dataset:** BDD100K + `img2blur` (夜間/弱光強化)
- **Computer Vision:** OpenCV (MJPEG 串流與影像預處理)
- **Generative AI:** Gemini 2.5 Flash (於 App 端執行數據分析)

## Connectivity & Protocols
- **Network Mode:** Wi-Fi Access Point (Pi 5 建立獨立熱點)
- **Primary App Connection:** Bluetooth SPP (Serial Port Profile)
- **Data Distribution (Pi 5 -> Zero):** UDP (Port 5005) 廣播
- **Control & Sync (Pi 5 <-> Mobile):** WebSocket (Port 8765)
- **Remote Dev:** SSH (`pi5@pi5`, `pi@pi`) Password(`1234`)

## App Development
- **Frontend:** React 18 (CDN), Tailwind CSS (CDN)
- **Platform:** Web App (PWA) / WebView
