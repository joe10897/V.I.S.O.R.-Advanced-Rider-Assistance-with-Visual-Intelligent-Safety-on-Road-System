# V.I.S.O.R. — Visor Intelligent Smart Operations & Reporting
### 智慧型二輪載具主動安全輔助、邊緣視覺感知與光學抬頭顯示系統

![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Raspberry Pi](https://img.shields.io/badge/Raspberry%20Pi-5%20%7C%20Zero%202W-C51A4A?style=for-the-badge&logo=raspberry-pi&logoColor=white)
![ONNX Runtime](https://img.shields.io/badge/ONNX%20Runtime-Edge%20AI-005CED?style=for-the-badge&logo=onnx&logoColor=white)
![React](https://img.shields.io/badge/Mobile%20App-React%20%7C%20Cordova-61DAFB?style=for-the-badge&logo=react&logoColor=black)
![Bluetooth](https://img.shields.io/badge/Comm-WebSocket%20%7C%20RFCOMM%20%7C%20UDP-0082FC?style=for-the-badge&logo=bluetooth&logoColor=white)

**V.I.S.O.R. (Visor Intelligent Smart Operations & Reporting)** 是一套專為台灣高密度二輪車流環境量身打造的**分散式邊緣運算機車主動安全輔助系統 (Motorcycle ADAS)**。系統以 **Raspberry Pi 5** 作為車載 AI 視覺與通訊中樞，結合 **Raspberry Pi Zero 2W** 安全帽光學反射式抬頭顯示器（HUD）以及 **Android 跨平台戰術行動端 App**，為騎士提供全天候前後雙鏡頭盲點偵測（BSD）、前方防撞預警（FCW）、車道偏移感知、測速照相提醒、哨兵行車紀錄以及事故 E-SOS 自動求救功能。

---

## 📑 目錄 (Table of Contents)

- [系統設計理念與核心亮點](#-系統設計理念與核心亮點)
- [系統架構與通訊拓樸](#-系統架構與通訊拓樸)
- [核心技術與子系統詳解](#-核心技術與子系統詳解)
  - [1. 邊緣視覺感知管線 (Edge AI Vision Pipeline)](#1-邊緣視覺感知管線-edge-ai-vision-pipeline)
  - [2. 空間幾何融合與 TTC 威脅分級 (SpatialFusion v2)](#2-空間幾何融合與-ttc-威脅分級-spatialfusion-v2)
  - [3. 光學反射式抬頭顯示器 (V.I.S.O.R. HUD)](#3-光學反射式抬頭顯示器-visor-hud)
  - [4. 雙通道零延遲容錯通訊架構 (Dual-Channel Comm)](#4-雙通道零延遲容錯通訊架構-dual-channel-comm)
  - [5. 哨兵模式、車載黑盒子與 E-SOS 緊急救援](#5-哨兵模式車載黑盒子與-e-sos-緊急救援)
  - [6. 戰術行動端應用程式 (Tactical Mobile App)](#6-戰術行動端應用程式-tactical-mobile-app)
- [AI 模型效能基準與實驗數據](#-ai-模型效能基準與實驗數據)
- [硬體規格與接線配置](#-硬體規格與接線配置)
- [專案目錄結構](#-專案目錄結構)
- [安裝與快速啟動指南](#-安裝與快速啟動指南)
- [系統參數配置說明 (`config.json`)](#-系統參數配置說明-configjson)
- [自動化部署與硬體診斷測試](#-自動化部署與硬體診斷測試)

---

## ✨ 系統設計理念與核心亮點

在台灣高密度的混合車流中，機車騎士面臨「後視鏡盲區大」、「轉頭查看路況導致視線離開前方」以及「突發逼車與急煞反應時間極短」三大安全痛點。V.I.S.O.R. 透過軟硬體深度協同設計解決上述問題：

* **🎯 專為台灣路況微調的 Edge AI 模型 (`YOLOv26n-TW Titan`)**
  結合台灣道路實景與夜間盲點資料集（共 3,638 張標註影像，修正大面積重疊與誤標問題），針對 `pedestrian`（行人）、`scooter`（機車）、`car`（汽車）、`bicycle`（自行車）、`truck`（大型車/公車/貨車）進行 5 類別精準辨識。
* **⚡ 非對稱式乒乓排程器 (Asymmetric Ping-Pong AI Scheduler)**
  在無獨立 GPU 的 Raspberry Pi 5 上，以 20Hz 主迴圈交替執行前後雙鏡頭推論；當後方出現連續逼近危險（Danger Streak）時，自動提高後鏡頭防禦推論優先級。
* **📐 單目視覺測距與卡爾曼濾波 TTC 預警 (`SpatialFusion v2`)**
  無需昂貴光達（LiDAR）或毫米波雷達，依據各車種真實物理寬度與 Sony IMX662 雙鏡頭焦距（前 120° / 後 173° 廣角）進行單目距離估計，結合 Kalman EMA 相對速度追蹤與碰撞時間（Time-to-Collision, TTC）演算法，實現零硬體成本的 4 級防撞預警。
* **🥽 安全帽光學反射式 HUD (`SSD1306 / SH1106 128×64 OLED`)**
  內建水平鏡像（Mirror）與垂直翻轉（Vertical Flip）光學矩陣轉換，配合多重單播/廣播自動探測機制（Unicast + Broadcast Auto-Discovery），確保在熱點、公共 Wi-Fi 或實體線材環境下皆能維持 20 FPS 穩定顯示與 `<5ms` 同步延遲。
* **🛡️ Wi-Fi WebSocket + 原生藍牙 RFCOMM 雙通道無感切換**
  內建 D-Bus 免螢幕自動配對代理人（`visor_bt_agent.py`），解決車載無頭（Headless）環境下新手機配對問題；藍牙端採用單一指令佇列執行緒與 512-byte 原子化分塊傳輸，徹底杜絕執行緒洩漏（Thread Exhaustion）與 JSON 黏包問題。

---

## 🏗️ 系統架構與通訊拓樸

本系統由三大獨立硬體節點與雲端分析資料庫組成，透過異質網路協議進行低延遲協同運作：

```mermaid
flowchart TB
    subgraph Sensors["📷 雙鏡頭與感測輸入層 (Sensors)"]
        CamFront["前向廣角鏡頭 (Front Cam)<br/>Sony IMX662 STARVIS 2<br/>FOV 120° | f=260"]
        CamRear["後向超廣角鏡頭 (Rear Cam)<br/>Sony IMX662 STARVIS 2<br/>FOV 173° | f=185"]
    end

    subgraph Pi5["🧠 V.I.S.O.R. Core 車載運算中樞 (Raspberry Pi 5)"]
        FrameReader["FrameReader 雙路非同步擷取<br/>V4L2 VIDIOC_QUERYCAP 節點過濾"]
        Scheduler["Asymmetric Ping-Pong 排程器<br/>20Hz 雙鏡頭交替推論與威脅鎖定"]
        
        subgraph AIPipeline["VisorCore 邊緣視覺引擎"]
            YOLO["YOLOv26n-TW Titan<br/>5-Class 台灣車流物件偵測"]
            Lane["車道線感知引擎<br/>CV-Magnet (0.4ms) / LSTR / UFLD v2"]
            Fusion["SpatialFusion v2<br/>單目測距 + Kalman EMA 相對速度 + TTC"]
        end

        Recorder["DashcamRecorder 哨兵循環錄影<br/>衝擊/傾角觸發事件鎖檔"]
        TripLogger["TripLogger 車載黑盒子<br/>非同步雙緩衝 CSV 紀錄 (<0.1% CPU)"]
        
        CommHub["多協定通訊匯流排<br/>WebSocket (8765) | BT RFCOMM (Ch.1) | UDP (5005/5006)"]
    end

    subgraph PiZero["🥽 V.I.S.O.R. HUD 抬頭顯示端 (Raspberry Pi Zero 2W)"]
        HudClient["HudClient 接收與渲染引擎<br/>多路心跳回報 (pi5.local / 192.168.4.1)"]
        OLED["1.3\" / 0.96\" I2C OLED (128x64)<br/>SSD1306 / SH1106 光學鏡像與反白閃爍警示"]
    end

    subgraph MobileApp["📱 V.I.S.O.R. 戰術行動端 (Android Cordova / React)"]
        UI["戰術儀表板與雙鏡頭即時預覽<br/>Tactical Log / 遠端電源與 HUD 調光控制"]
        Geo["GPS 測速照相預警系統<br/>全台測速點位資料庫 + Haversine 距離解算"]
        ESOS["E-SOS 緊急救援模組<br/>嚴重傾倒偵測自動發送求救簡訊"]
    end

    subgraph Cloud["☁️ 雲端數據分析層"]
        Supabase[("Supabase 雲端資料庫<br/>騎乘軌跡 / 急煞 / 超速 / 傾角統計")]
    end

    CamFront --> FrameReader
    CamRear --> FrameReader
    FrameReader --> Scheduler
    FrameReader --> Recorder
    Scheduler --> YOLO
    Scheduler --> Lane
    YOLO --> Fusion
    Lane --> Fusion
    Fusion --> TripLogger
    Fusion --> CommHub

    CommHub -- "UDP Broadcast/Unicast :5005 (20Hz 遙測與威脅)" --> HudClient
    HudClient -- "UDP Heartbeat :5006 (狀態與 IP 回報)" --> CommHub
    HudClient -- "I2C (0x3C)" --> OLED

    CommHub <-- "Wi-Fi WebSocket :8765 / Bluetooth RFCOMM Ch.1" --> UI
    UI --> Geo
    UI --> ESOS
    UI <-- "REST / Realtime Sync" --> Supabase
```

---

## 🔬 核心技術與子系統詳解

### 1. 邊緣視覺感知管線 (Edge AI Vision Pipeline)
位於 [`YOLOv26_DEMO/`](file:///C:/Users/USER/Desktop/motorcycle_assist/YOLOv26_DEMO) 與 [`vision/`](file:///C:/Users/USER/Desktop/motorcycle_assist/vision) 目錄中，由 [`VisorCore`](file:///C:/Users/USER/Desktop/motorcycle_assist/YOLOv26_DEMO/visor_core.py) 統一封裝：
* **V4L2 硬體層級防衝突擷取 ([`vision/frame_reader.py`](file:///C:/Users/USER/Desktop/motorcycle_assist/vision/frame_reader.py))**：透過 Linux `ioctl(VIDIOC_QUERYCAP)` 直接檢驗 `/dev/video*` 設備旗標，精準過濾 UVC Metadata 虛擬節點（`V4L2_CAP_META_CAPTURE`），並具備前後鏡頭同節點防衝突自動降級保護。
* **台灣道路專用物件偵測 ([`YOLOv26_DEMO/engine_yolo26.py`](file:///C:/Users/USER/Desktop/motorcycle_assist/YOLOv26_DEMO/engine_yolo26.py))**：採用 `YOLOv26n-TW Titan` ONNX/PyTorch 模型，支援非正方形矩形推論（`imgsz: [288, 384]`，`rect: true`），大幅降低背景天空與無效邊緣的算力浪費。
* **三模態可切換車道線引擎**：
  * **CV-Magnet ([`engine_cv_lane.py`](file:///C:/Users/USER/Desktop/motorcycle_assist/YOLOv26_DEMO/engine_cv_lane.py))**：預設啟用之超輕量幾何地面吸附車道線演算法，單幀耗時僅 **0.4ms**，零深度學習額外負載。
  * **LSTR ([`engine_lstr.py`](file:///C:/Users/USER/Desktop/motorcycle_assist/YOLOv26_DEMO/engine_lstr.py))**：基於 Transformer 與 CULane 曲線有理函數（Rational Function）之車道預測模型（僅 0.77M 參數），內建對數空間取樣（Logspace Y-Sampling）、EMA 平滑濾波與 15 幀慣性滑行（Inertia Coasting），於路口或斑馬線短暫無標線時仍能穩定維持車道邊界。
  * **UFLD v2 ([`engine_ufld.py`](file:///C:/Users/USER/Desktop/motorcycle_assist/YOLOv26_DEMO/engine_ufld.py))**：支援 FP32/FP16 量化與 Skip-Frame 跳幀快取的高精度行錨點車道偵測。

### 2. 空間幾何融合與 TTC 威脅分級 (`SpatialFusion v2`)
位於 [`YOLOv26_DEMO/spatial_fusion.py`](file:///C:/Users/USER/Desktop/motorcycle_assist/YOLOv26_DEMO/spatial_fusion.py)，負責將 2D 邊界框與車道多邊形轉化為符合 ADAS 標準的防撞決策：
* **分車種類別單目距離解算**：摒棄傳統固定車寬假設，依類別賦予真實物理寬度（`scooter: 0.7m`、`car: 1.8m`、`truck: 2.5m`、`bicycle: 0.6m`、`pedestrian: 0.5m`），並針對前後鏡頭不同焦距（前 `f=260`、後 `f=185`）與車尾邊緣偏移（`-3m` 修正）精確換算實質車距：
  $$\text{Distance} = \frac{W_{\text{class}} \times f_{\text{camera}}}{W_{\text{bbox}}}$$
* **Kalman EMA 無感測器相對速度追蹤**：透過跨幀目標中心點匹配與指數移動平均（$\alpha = 0.4$）計算逼近相對速度 $v_{\text{rel}} = \Delta d / \Delta t$，進一步求取碰撞時間 $\text{TTC} = d / v_{\text{rel}}$。
* **四級威脅判定與側向防干擾門檻**：側向盲區（Left / Right）最高僅觸發視覺提醒（`CAUTION`），避免市區併行車流造成過度警報；正前方急煞與正後方逼車則依 TTC 與絕對距離上限（Distance Caps）分級：

| 威脅等級 (Threat Level) | 碰撞時間門檻 (TTC) | 絕對距離上限 (Dist Cap) | 車道位置限制 (Lane Gating) | HUD 與系統行為 |
| :--- | :---: | :---: | :---: | :--- |
| 🔴 **`CRITICAL`** | `< 1.0 s` | `< 2.0 m` | 僅限本車道 (`IN_LANE`) / 正後方 | 緊急危險警報、HUD 全螢幕硬體反白閃爍 |
| 🟠 **`WARNING`** | `< 1.5 s` | `< 4.0 m` | 僅限本車道 (`IN_LANE`) / 正後方 | 防撞預警提示、HUD 方向箭頭強化警示 |
| 🟡 **`CAUTION`** | `< 2.5 s` | `< 8.0 m` | 本車道 / 鄰近車道盲區 (`BSD`) | 盲點注意提醒（純視覺標示，不觸發刺耳蜂鳴） |
| 🟢 **`SAFE`** | `≥ 2.5 s` | `≥ 8.0 m` | 所有其他區域 | 常規狀態顯示 |

### 3. 光學反射式抬頭顯示器 (V.I.S.O.R. HUD)
位於 [`hud/hud_client.py`](file:///C:/Users/USER/Desktop/motorcycle_assist/hud/hud_client.py)，運行於 Raspberry Pi Zero 2W：
* **光學分光鏡座標轉換 (`HudCanvas`)**：支援透過設定檔或 App 即時切換水平鏡像（`mirror`）與垂直翻轉（`flip_v`），確保影像投射至安全帽反射片時文字方向完全正立。
* **三執行緒零積壓架構**：
  1. **Network Thread**：非阻塞式清空 UDP Socket 緩衝區，永遠只保留最新一幀封包，徹底消除網路延遲累積。
  2. **Render Thread**：穩定維持 20 FPS 畫面刷新，顯示時速、時間、導航方向、測速照相距離、四向威脅箭頭（`/\`, `\/`, `<`, `>`），並在 `danger` 狀態下以 `0.35s` 週期觸發 OLED 硬體級別反白閃爍（Hardware Invert Flash）。
  3. **Heartbeat Thread**：每 2 秒主動向 `pi5.local`、`192.168.4.1` 與 `255.255.255.255` 發送多路心跳封包（Port `5006`），讓 Pi 5 自動鎖定 HUD 真實 IP 並切換為高速單播（Unicast）。

### 4. 雙通道零延遲容錯通訊架構 (Dual-Channel Comm)
位於 [`communication/`](file:///C:/Users/USER/Desktop/motorcycle_assist/communication) 與 [`visor_bt_agent.py`](file:///C:/Users/USER/Desktop/motorcycle_assist/visor_bt_agent.py)：
* **WebSocket 高速通道 ([`websocket_server.py`](file:///C:/Users/USER/Desktop/motorcycle_assist/communication/websocket_server.py))**：監聽 Port `8765`，支援 `SO_REUSEADDR` / `SO_REUSEPORT` 快速重啟，負責傳送高頻遙測數據與雙鏡頭即時壓縮影像串流。
* **原生藍牙 RFCOMM 抗斷訊伺服器 ([`bluetooth_server.py`](file:///C:/Users/USER/Desktop/motorcycle_assist/communication/bluetooth_server.py))**：
  * **指令佇列化工作執行緒 (`_command_worker`)**：以單一常駐佇列處理手機端 4Hz `telemetry_sync` 指令，徹底解決傳統架構每指令衍生新執行緒導致的 Linux 核心資源耗盡問題。
  * **原子化分塊與防堵塞看門狗**：以 512 Bytes 分塊平滑寫入 RFCOMM Socket，具備自動補齊換行符與連續逾時自我重連機制，根除藍牙 JSON 黏包（Sticky Packets）。
* **免螢幕藍牙自動配對代理人 ([`visor_bt_agent.py`](file:///C:/Users/USER/Desktop/motorcycle_assist/visor_bt_agent.py))**：透過 `org.bluez.Agent1` 註冊 `NoInputNoOutput` 代理，新手機連線時自動確認配對碼並寫入 `Trusted` 白名單，實現真正的車載無頭（Headless）隨連即用。

### 5. 哨兵模式、車載黑盒子與 E-SOS 緊急救援
* **哨兵循環錄影 ([`vision/recorder.py`](file:///C:/Users/USER/Desktop/motorcycle_assist/vision/recorder.py))**：平時於記憶體維護環形緩衝區（Circular Buffer），當偵測到異常震動、傾角超標或緊急威脅時，自動將事件前後關鍵影像封裝寫入 `events/` 與 `recordings/`。
* **非同步車載黑盒子 ([`trip_logger.py`](file:///C:/Users/USER/Desktop/motorcycle_assist/trip_logger.py))**：採用 `Queue + Daemon Worker Thread` 架構，主迴圈寫入耗時 **0ms**（CPU 佔用率 `<0.1%`），自動統計單趟行程之最高/平均車速、FCW/BSD 觸發次數、最小逼近距離與各車種感知分佈，並支援自動產出結構化路測報告。

### 6. 戰術行動端應用程式 (Tactical Mobile App)
位於 [`www/`](file:///C:/Users/USER/Desktop/motorcycle_assist/www)，基於 **React + TailwindCSS + Recharts + Leaflet + Apache Cordova** 構建：
* **即時戰術儀表板**：整合前後雙鏡頭即時串流預覽、雷達威脅方位視覺化、車速與車身傾角儀表。
* **全台測速照相預警 ([`www/lib/js/GeoUtils.js`](file:///C:/Users/USER/Desktop/motorcycle_assist/www/lib/js/GeoUtils.js))**：內建離線全台測速照相座標資料庫（[`speed_cameras.json`](file:///C:/Users/USER/Desktop/motorcycle_assist/www/lib/data/speed_cameras.json)），即時解算騎士與前方測速點距離並同步推播至安全帽 HUD。
* **硬體遠端控制與調光優化**：提供 HUD 顯示項目開關、OLED 亮度滑桿（採用 `onMouseUp`/`onTouchEnd` 放手發送機制避免封包風暴），以及 Pi 5 / Pi Zero 2W 雙裝置遠端安全關機按鈕。
* **雲端騎乘大數據分析**：整合 **Supabase** 雲端同步，自動彙整歷史騎乘紀錄、超速、急煞與大傾角事件圖表。

---

## 📊 AI 模型效能基準與實驗數據

以下數據摘錄自本專案完整實驗報告（詳見 [`YOLOv26_DEMO/BENCHMARK_REPORT.md`](file:///C:/Users/USER/Desktop/motorcycle_assist/YOLOv26_DEMO/BENCHMARK_REPORT.md)）：

### 物件偵測模型比較 (Object Detection Benchmark)

| 模型版本 (Model Variant) | 輸入解析度 | Precision | Recall | F1-Score | mAP@50 | 參數量 | 模型大小 | 推論速度 (Pi 5 預估 / 實測) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **YOLOv8n (Base)** | 640 px | 0.421 | 0.285 | 0.340 | 0.298 | 3.2 M | 6.20 MB | 5–8 FPS (>150ms) |
| **YOLOv8n (Optimized)** | 320 px | 0.543 | 0.326 | 0.407 | 0.336 | 3.2 M | 6.20 MB | 15–20 FPS (<60ms) |
| **YOLOv26n (COCO Pretrained)** | 320 px | 0.561 | 0.338 | 0.422 | 0.349 | 2.6 M | 5.30 MB | 20–25 FPS (<45ms) |
| **YOLOv26n-TW Titan ★ (本研究微調)** | 288×384 (rect) | **0.733** | **0.610** | **0.666** | **0.663** | **2.6 M** | **5.16 MB** | **~20 FPS (Ping-Pong 雙鏡穩定)** |

### 車道線與完整感知管線延遲比較 (Full Pipeline Comparison)

| 車道線引擎配置 | 執行後端 | 參數規模 | 測距與威脅邏輯 | 單幀延遲 (Desktop CPU) | 整體 FPS (Desktop / Pi 5) |
| :--- | :---: | :---: | :--- | :---: | :---: |
| **UFLD v2 (FP32)** | ONNX Runtime | 12.0 M | 固定車寬 1.8m | 262 ms | 3.8 FPS / ~1.3 FPS |
| **UFLD v2 (FP16 + Skip-2)** | ONNX Runtime | 12.0 M | 固定車寬 1.8m | 147 ms | 6.8 FPS / ~2.3 FPS |
| **LSTR CULane (Edge Skip-2)** | TorchScript | **0.77 M** | **分車種寬度 + TTC + Kalman EMA** | **29 ms** | **34.7 FPS / ~10.8 FPS** |
| **CV-Magnet (Ground-Snapping) ★** | Native OpenCV | **0 M** | **分車種寬度 + TTC + Kalman EMA** | **~19.4 ms** | **50+ FPS / ~20 FPS** |

---

## 🛠️ 硬體規格與接線配置

### 1. 硬體清單 (Bill of Materials)
* **車載主機 (V.I.S.O.R. Core)**：Raspberry Pi 5 (8GB LPDDR4X, Cortex-A76 四核心 @ 2.4GHz)
* **影像感測器 (Dual Cameras)**：Sony IMX662 STARVIS 2 夜視星光級雙鏡頭模組（USB 2.0 UVC / MIPI-CSI）
  * **前鏡頭 (Front ADAS)**：120° 廣角、等效焦距 `f=260`
  * **後鏡頭 (Rear BSD)**：173° 超廣角、等效焦距 `f=185`
* **抬頭顯示器 (V.I.S.O.R. HUD)**：Raspberry Pi Zero 2W + 1.3 吋 / 0.96 吋 I2C OLED 顯示模組（`SSD1306` 或 `SH1106` 驅動晶片，解析度 `128×64`）
* **行動終端 (Mobile App)**：Android 智慧型手機（支援 Bluetooth SPP 與 Wi-Fi）

### 2. Pi Zero 2W 與 I2C OLED 接線表 (Pinout)

| OLED 模組腳位 | Raspberry Pi Zero 2W 腳位 | GPIO 編號 | 說明 |
| :---: | :---: | :---: | :--- |
| **VCC / VDD** | Pin 1 | 3.3V Power | 3.3V 電源供應 |
| **GND** | Pin 6 | Ground | 共通接地 |
| **SCL / SCK** | Pin 5 | GPIO 3 (SCL1) | I2C 時脈訊號線 |
| **SDA** | Pin 3 | GPIO 2 (SDA1) | I2C 資料訊號線 (`預設位址 0x3C`) |

---

## 📂 專案目錄結構

```text
motorcycle_assist/
├── main_controller.py          # V.I.S.O.R. Core 車載主控制器 (整合雙鏡頭、AI 排程、通訊與錄影)
├── main.py                     # 獨立視覺展示與快速測試入口
├── config.json                 # 系統全域參數配置檔 (網路埠號、相機參數、距離閾值、HUD 設定)
├── config_loader.py            # 設定檔非同步載入與持久化儲存工具
├── trip_logger.py              # 非同步雙緩衝車載黑盒子路測記錄器 (0ms 阻塞、CSV 匯出)
├── visor_bt_agent.py           # BlueZ D-Bus 免螢幕藍牙自動配對與信任代理人
├── requirements.txt            # Python 核心套件依賴清單
├── package.json                # Node.js / esbuild 與 Apache Cordova 專案設定
├── config.xml                  # Apache Cordova Android App 打包組態檔
│
├── YOLOv26_DEMO/               # 邊緣視覺感知核心模組 (VisorCore Pipeline)
│   ├── visor_core.py           # 前後雙鏡頭 AI 推論與四向威脅轉換封裝介面
│   ├── engine_yolo26.py        # YOLOv26n-TW 台灣道路物件偵測引擎
│   ├── engine_cv_lane.py       # CV-Magnet 0.4ms 極速地面幾何車道線引擎
│   ├── engine_lstr.py          # LSTR Transformer 車道曲線預測引擎 (含 TorchScript 與慣性滑行)
│   ├── engine_ufld.py          # UFLD v2 ONNX 車道線偵測引擎
│   ├── spatial_fusion.py       # SpatialFusion v2 單目測距、Kalman EMA 相對速度與 TTC 威脅引擎
│   ├── visualizer_hud.py       # 視覺化戰術 HUD 疊加渲染器
│   ├── main_demo.py            # 多模型命令列基準測試與展示工具
│   └── BENCHMARK_REPORT.md     # 完整模型精準度、延遲與極端氣候實驗報告
│
├── vision/                     # 硬體相機擷取與哨兵錄影模組
│   ├── frame_reader.py         # V4L2 節點過濾、USB/CSI 自動探測與非同步影像讀取器
│   ├── recorder.py             # 環形緩衝區行車紀錄與碰撞/傾倒事件觸發錄影器
│   ├── detector.py             # 基礎 YOLO 偵測器介面
│   ├── tracker.py              # 多目標追蹤輔助模組
│   ├── fusion.py               # 基礎幾何距離融合計算
│   └── sensor_sim.py           # 展覽與開發模式虛擬感測器模擬器 (車速、傾角、G 值)
│
├── communication/              # 跨節點雙向通訊協定層
│   ├── websocket_server.py     # 高速非同步 WebSocket 伺服器 (Port 8765)
│   ├── bluetooth_server.py     # 原生 RFCOMM 藍牙伺服器 (單一佇列執行緒 + 512B 分塊防黏包)
│   ├── udp_broadcaster.py      # 20Hz 恆定背景執行緒 UDP 廣播/單播發射器 (Port 5005)
│   └── udp_listener.py         # HUD 心跳與狀態回報監聽器 (Port 5006)
│
├── hud/                        # 安全帽抬頭顯示器模組 (Pi Zero 2W)
│   └── hud_client.py           # I2C OLED (SSD1306/SH1106) 渲染引擎、光學翻轉與多路心跳客戶端
│
├── www/                        # 戰術行動端應用程式前端 (React + TailwindCSS + Cordova)
│   ├── index.html              # App 主入口頁面 (整合儀表板、雙鏡串流、雲端分析、HUD 控制)
│   ├── build.mjs               # esbuild 前端快速打包腳本
│   ├── js/                     # React 組件原始碼 (app.jsx) 與打包產物
│   └── lib/                    # 離線前端庫與全台測速照相資料庫 (GeoUtils.js, speed_cameras.json)
│
├── scripts/                    # 自動化部署、硬體診斷與 Systemd 系統服務腳本
│   ├── visor-core.service      # Pi 5 開機自動啟動 Systemd 服務單元
│   ├── visor-hud.service       # Pi Zero 2W 開機自動啟動 Systemd 服務單元
│   ├── deploy_pi5.sh           # Pi 5 環境部署腳本
│   ├── deploy_pizero.sh        # Pi Zero 2W 環境部署腳本
│   ├── setup_ap.sh             # Pi 5 車載 Wi-Fi 熱點 (Access Point) 建置腳本
│   ├── setup_bt.sh             # 藍牙 SPP 服務與權限初始化腳本
│   └── diag_*.py               # 雙 USB / 雙 CSI 相機與 OLED 硬體檢測工具
│
├── tools/                      # 開發輔助與模型匯出工具
│   ├── build_visor_titan.py    # YOLOv26n-TW Titan 模型訓練與 ONNX 匯出工具
│   ├── hud_simulator.py        # 電腦端 HUD 封包接收模擬器
│   └── test_clients.py         # WebSocket / UDP 通訊壓力測試客戶端
│
└── tests/                      # 自動化單元測試與端對端整合測試 (Pytest)
    ├── test_main_controller.py
    ├── test_hud_e2e_integration.py
    ├── test_hud_heartbeat.py
    ├── test_road_ready_integration.py
    ├── test_exhibition_and_hardware.py
    ├── test_sentry_mode.py
    └── test_trip_logger.py
```

---

## 🚀 安裝與快速啟動指南

### 1. 車載核心端設定 (Raspberry Pi 5 — V.I.S.O.R. Core)

```bash
# 1. 複製專案儲存庫
git clone https://github.com/joe10897/Visor.git motorcycle_assist
cd motorcycle_assist

# 2. 安裝系統層級相依套件 (藍牙、V4L2 與 OpenCV 依賴)
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip python3-dbus python3-gi \
                        bluez bluez-tools v4l-utils libgl1

# 3. 建立虛擬環境並安裝 Python 套件
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install psutil onnxruntime

# 4. 啟動 V.I.S.O.R. 主控制器
# 實車模式 (自動掛載前後雙鏡頭、WebSocket、藍牙與 UDP 廣播)
python main_controller.py

# 展示模式 (使用範例影片與模擬感測數據)
python main_controller.py --demo

# 展覽自動循環模式 (Exhibition Mode)
python main_controller.py --exhibition
```

### 2. 抬頭顯示器端設定 (Raspberry Pi Zero 2W — V.I.S.O.R. HUD)

```bash
# 1. 啟用 Raspberry Pi I2C 介面
sudo raspi-config nonint do_i2c 0

# 2. 安裝 OLED 驅動與繪圖函式庫
sudo apt-get update
sudo apt-get install -y python3-pip python3-pil python3-smbus i2c-tools
pip3 install luma.oled

# 3. 確認 I2C OLED 位址 (預設為 0x3c)
sudo i2cdetect -y 1

# 4. 啟動 HUD 客戶端 (預設開啟水平鏡像以配合安全帽反射片)
python3 hud/hud_client.py --model SSD1306
```

### 3. 行動端 App 建置與封裝 (Android APK / Web)

```bash
# 1. 安裝前端與 Cordova 依賴
npm install

# 2. 編譯前端 JSX 資源
npm run build

# 3. 打包 Android APK (需具備 Android SDK 與 Java 17 環境)
npx cordova build android
```
> 💡 **快速預覽**：開發階段亦可直接以瀏覽器開啟 [`www/index.html`](file:///C:/Users/USER/Desktop/motorcycle_assist/www/index.html)，在介面中輸入 Pi 5 IP（預設熱點為 `192.168.4.1`）即可透過 WebSocket 即時連線。

---

## ⚙️ 系統參數配置說明 (`config.json`)

系統所有執行期參數皆集中管理於 [`config.json`](file:///C:/Users/USER/Desktop/motorcycle_assist/config.json)，並支援透過手機 App 遠端即時熱更新：

| 分類區段 | 參數名稱 | 預設值 | 功能說明 |
| :--- | :--- | :---: | :--- |
| **`network`** | `broadcast_ip` | `"255.255.255.255"` | UDP 通用廣播位址（收到 HUD 心跳後自動加入單播目標） |
| | `udp_port` | `5005` | Pi 5 發送至 Pi Zero HUD 之遙測數據埠號 |
| | `hud_listener_port` | `5006` | Pi 5 監聽來自 Pi Zero HUD 心跳回報之埠號 |
| | `websocket_port` | `8765` | 行動端 App WebSocket 雙向連線埠號 |
| **`vision`** | `source_front` / `rear` | `"/dev/video0"` / `"2"` | 前後鏡頭 V4L2 裝置節點（支援自動探測回退） |
| | `fov_front` / `fov_rear` | `120` / `173` | 前後鏡頭水平視角（度），用於空間盲區象限切分 |
| | `focal_length_front` / `rear` | `260` / `185` | 前後鏡頭單目測距像素焦距常數 |
| | `model_path` | `"models/yolo26n_tw_titan.onnx"` | 主力邊緣推論模型權重路徑 |
| | `lane_model` | `"cv_magnet"` | 車道線引擎選擇（`"cv_magnet"` / `"lstr"` / `"ufld"`） |
| | `imgsz` | `[288, 384]` | 模型推論輸入解析度（支援矩形加速） |
| **`thresholds`** | `danger_dist` | `10.0` | 緊急危險警報觸發距離門檻（公尺） |
| | `warning_dist` | `25.0` | 防撞注意預警觸發距離門檻（公尺） |
| | `tilt_alert` | `18.0` | 車身異常傾倒 / E-SOS 觸發角度門檻（度） |
| **`hud_config`** | `mirror` / `flip_v` | `true` / `false` | 安全帽光學反射鏡像與垂直翻轉開關 |
| | `brightness` | `128` | OLED 螢幕對比亮度（`0–255`，支援 App 遠端無段調光） |
| | `oled_model` | `"SSD1306"` | OLED 驅動晶片型號（支援 `"SSD1306"` 與 `"SH1106"`） |

---

## 🧪 自動化部署與硬體診斷測試

### 註冊 Systemd 開機自動啟動服務
```bash
# 於 Raspberry Pi 5 安裝核心服務與藍牙自動配對服務
sudo bash scripts/install_service.sh
sudo systemctl enable --now visor-core

# 於 Raspberry Pi Zero 2W 安裝 HUD 顯示服務
sudo cp scripts/visor-hud.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now visor-hud
```

### 執行自動化測試套件 (Pytest)
專案內建涵蓋通訊協定、HUD 心跳同步、哨兵錄影、黑盒子記錄器與硬體容錯之完整測試套件：
```bash
pytest tests/ -v
```

### 硬體診斷工具集
* **雙 USB 鏡頭頻寬與節點檢測**：`python scripts/diag_dual_usb.py`
* **雙 MIPI-CSI 鏡頭檢測**：`python scripts/diag_dual_csi.py`
* **OLED 顯示器與光學翻轉硬體測試**：`python scripts/test_oled_hardware.py`
* **HUD 動態威脅與閃爍模擬測試**：`python scripts/test_hud_demo.py`

---

## 📄 授權與開發團隊 (License & Credits)

* **專案名稱**：V.I.S.O.R. (Visor Intelligent Smart Operations & Reporting)
* **開發團隊**：Joe10897 / V.I.S.O.R. Team
* **GitHub Repository**：[https://github.com/joe10897/Visor](https://github.com/joe10897/Visor)
