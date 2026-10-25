# Product Definition: V.I.S.O.R. (Visual Intelligent Safety On Road)

## Initial Concept
V.I.S.O.R. 是一套基於 Raspberry Pi 5 邊緣運算與 AI 影像辨識的機車全方位防護系統。系統整合了 AI 物件偵測、碰撞預警、哨兵模式，並透過分散式運算架構與多端裝置（手機 App、Pi Zero HUD）連動。本專案將參與發明展與各類競賽，展現高度的技術整合與創新。

## Target Audience
- 追求主動安全防護的機車騎士。

## Core Features
- **主動安全與 AI 視覺 (Active Safety & AI Vision)**
    - **高效能物件偵測：** 使用 YOLOv8n 模型，針對 BDD100K 資料集進行優化。
    - **台灣在地化與環境強化：** 針對台灣常見的「速克達」優化偵測，並利用 `img2blur` 資料集提升夜間/弱光表現。
    - **目標類別：** 2:Car, 3:Motorcycle, 5:Bus, 7:Truck。
    - **警示邏輯：** 基於 Bounding Box 面積佔比 (Area Ratio > 0.25) 判斷距離，並計算 TTC (Time-to-Collision)。

- **分散式通訊架構 (Network & Connectivity)**
    - **Wi-Fi AP 獨立熱點：** Pi 5 作為 Gateway (192.168.4.1)，建立 VISOR_Net。
    - **混合通訊模式：** 支援藍牙 SPP (Serial Port Profile) 與 Wi-Fi 雙重連線，確保 App 隨時可用。
    - **低延遲數據分發：** 透過 UDP (Port 5005) 將儀表數據即時廣播至 Pi Zero HUD。
    - **雙向同步：** 透過 WebSocket (Port 8765) 與 App 進行狀態同步與遠端設定。

- **智慧分析 (GenAI Integration)**
    - **Gemini 2.5 Flash：** 於 App 端整合，分析騎乘數據（急煞、傾角）提供戰術評語，或擔任智慧維修助手。

- **停車防護 (Sentry Mode)**
    - 利用 Pi 5 內建 IMU 偵測異常震動，自動錄影並在手機 App 再次連線時發送通知。

## System Architecture
- **Server (The Brain):** Raspberry Pi 5 (`ssh pi5@pi5`, pw: `1234`)
    - 負責 AI 推理、Wi-Fi 基地台、藍牙伺服器、雙 USB 鏡頭影像處理。
- **HUD (The Eyes):** Raspberry Pi Zero 2 W (`ssh pi@pi`, pw: `1234`)
    - 負責 OLED (SSD1306) 數據渲染，支援多種版面切換 (Standard, Sport, Minimal)。
- **Interface (The Console):** Android 手機 App (React/Tailwind)
    - 視覺化戰情室、參數設定與 SOS 功能。

## User Interaction
- **騎乘模式：** App 與 HUD 同時顯示即時警示、導航與車輛遙測數據。
- **停車模式：** 系統進入低功耗監測狀態，執行哨兵錄影。
- **同步與回顧：** 返車自動同步停車期間的異常事件。
