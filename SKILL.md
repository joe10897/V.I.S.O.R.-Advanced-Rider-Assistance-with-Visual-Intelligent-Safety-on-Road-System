---
name:V.I.S.O.R. (Visual Intelligent Safety On Road)
description:建構基於 AI 的機車前後防護與抬頭顯示 (HUD) 行車助理系統
---

1. 系統架構總覽 (System Architecture)

本系統採用 分散式運算架構，由中央運算單元 (Pi 5) 負責重度 AI 推理，並透過獨立的區域網路 (AP Mode) 分發數據至邊緣顯示裝置。

網路拓撲 (Network Topology)

模式: Wi-Fi Access Point (AP) 獨立熱點

SSID: VISOR_Net (或自定義)

IP 分配:

Server (Pi 5): 192.168.4.1 (固定 Gateway IP)

Clients: DHCP 自動分配 (範圍 192.168.4.x)

通訊協定 (Communication Protocols)


Pi 5 -> Pi Zero

UDP

5005

儀表板數據 (HUD)

廣播模式，極低延遲，射後不理


Pi 5 <-> Mobile APP

WebSocket

8765

App 儀表板與設定

雙向通訊，狀態同步，控制指令


Pi 5 -> Cloud

HTTPS

443

Gemini API

AI 戰術分析 (需外網時)


2. 硬體配置 (Hardware Stack)

A. 核心運算單元 (The Brain)

裝置: Raspberry Pi 5 
連接方法：
ssh pi5@pi5(password:1234)
# 進入虛擬環境
source venv/bin/activate
python main_controller.py

角色: AI 推理、Wi-Fi 基地台、數據中樞

外設:

雙 USB 鏡頭 (前/後，MJPEG 壓縮優化)

IMU 感測器 (MPU-6050, I2C)

B. 頭盔顯示單元 (The Eyes)

裝置: Raspberry Pi Zero 2 W
連接方法：
ssh pi@pi(password:1234)
source hud_env/bin/activate
oled_test.py

OS: Raspberry Pi OS Lite (64-bit)

角色: 輕量化數據接收與渲染

外設:

SSD1306 OLED 顯示器 (128x64, I2C)

有源蜂鳴器 (GPIO 控制，選配)

C. 控制介面 (The Interface)

裝置: 智慧型手機 (Android)

平台: Web App (PWA) / WebView

角色: 視覺化戰情室、參數設定、緊急求救 (SOS)

3. 軟體技能與實作細節 (Implementation Skills)

Server 端 (Python @ Pi 5)

核心語言: Python 3.10+

關鍵函式庫:

ultralytics: 執行 YOLOv26 TW Titan (台灣道路專用輕量化模型) 物件偵測。

opencv-python: 影像擷取、預處理、MJPEG 串流。

websockets: 建立 Async WebSocket Server。

socket: 建立 UDP Broadcast Socket。

threading / asyncio: 多執行緒並行處理 (AI 運算與網路傳輸分離)。

關鍵邏輯 (main_controller.py):

雙鏡頭批次推論 (Batch Inference)。

邊緣變形區域加權判斷 (針對廣角鏡)。

JSON 數據打包與分發。

HUD Client 端 (Python @ Pi Zero 2W)

核心語言: Python 3.9+

關鍵函式庫:

luma.oled: 驅動 SSD1306 OLED。

socket: 監聽 UDP 封包。

關鍵邏輯 (hud_display.py):

非阻塞式 (Non-blocking) 網路監聽。

Cyberpunk 風格 UI 繪製 (Pillow ImageFont)。

警示優先級渲染 (Warning Override)。

Mobile App 端 (React @ Mobile)

核心技術: HTML5, React 18 (CDN), Tailwind CSS (CDN)。

關鍵功能 (index.html):

WebSocket Client: 自動連線與斷線重連機制。

Gemini API: 整合 LLM 進行騎乘數據分析。

Responsive UI: 響應式手機介面設計。

Edge Lighting: CSS 動畫模擬視覺警示。

4. AI 部署策略 (AI Strategy)

視覺模型 (Computer Vision)

模型: YOLOv26 TW Titan (384x288 原生矩形輕量化模型)

輸入解析度: $640 \times 480$ (強制縮放以匹配 Pi 5 效能)

偵測類別 (COCO):

2: Car (汽車)

3: Motorcycle (機車)

5: Bus (公車)

7: Truck (卡車)

警示邏輯:

計算 Bounding Box 面積佔比 (Area Ratio)。

若 Ratio > 0.25 且位於後鏡頭 -> 觸發「逼車警示」。

生成式 AI (Generative AI)

模型: Gemini 2.5 Flash

用途:

騎乘戰情室: 分析急煞、傾角數據，生成評語。

智慧助理: 回答車輛維修、法規問題。

整合方式: 前端 (App) 直接呼叫 API，減輕 Pi 5 負擔。

5. 部署檢查清單 (Deployment Checklist)

✅ Pi 5 (Server)

[ ] 系統更新 (apt update && upgrade)

[ ] 設定固定 IP 與 AP 熱點 (nmcli)

[ ] 建立 Python 虛擬環境 (venv)

[ ] 安裝依賴 (ultralytics, opencv-python, websockets)

[ ] 部署 main_controller.py 並設定開機自啟 (Systemd)

✅ Pi Zero 2W (HUD)

[ ] 開啟 I2C 介面 (raspi-config)

[ ] 設定 wpa_supplicant.conf 連接 Pi 5 熱點

[ ] 安裝 OLED 驅動 (luma.oled)

[ ] 部署 hud_display.py 並設定開機自啟

✅ Mobile App

[ ] 設定 Gemini API Key

[ ] 連接 VISOR_Net Wi-Fi

[ ] 開啟瀏覽器訪問 App (或封裝為 APK)

版本: MK-XXV
維護者: V.I.S.O.R. Dev Team