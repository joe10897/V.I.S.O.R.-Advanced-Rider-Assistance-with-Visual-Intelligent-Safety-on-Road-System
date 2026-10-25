# Specification: Core Communication Infrastructure

## Goal
建立 V.I.S.O.R. 的核心通訊骨幹，實現 Pi 5 (Server) 對 Pi Zero (HUD) 的單向廣播與對 Mobile App 的雙向控制。此 Track 將產出部署用的腳本與核心通訊程式碼，為後續的 AI 整合奠定基礎。
多利用chrome-devtools-mcp作測試
## Scope
1. **系統配置腳本：**
   - 建立 `setup_ap.sh`：用於將 Pi 5 配置為 Wi-Fi AP 模式 (SSID: `VISOR_Net`)。
2. **通訊模組 (Communication Module)：**
   - `UdpBroadcaster`：負責將 JSON 數據封包透過 UDP (Port 5005) 廣播。
   - `WebSocketServer`：負責處理 App 連線 (Port 8765)，支援狀態查詢與指令接收。
3. **主控制器重構：**
   - 建立 `main_controller.py` 作為新的系統入口點。
   - 整合通訊模組，實現「接收感測數據 -> (預留 AI 處理位置) -> 廣播數據」的迴圈。

## Technical Details
- **Network:**
    - Gateway IP: `192.168.4.1`
    - Subnet Mask: `255.255.255.0`
- **UDP Protocol:**
    - Target: `<broadcast>` (255.255.255.255)
    - Port: `5005`
    - Format: JSON (Minified)
- **WebSocket Protocol:**
    - Host: `0.0.0.0`
    - Port: `8765`
    - Library: `websockets` (Asyncio based)

## Acceptance Criteria
- [ ] `setup_ap.sh` 能在乾淨的 Pi OS 上執行並成功建立熱點。
- [ ] `main_controller.py` 啟動後，能同時開啟 UDP 廣播與 WebSocket 服務。
- [ ] 提供測試腳本 `test_clients.py`，能模擬 HUD 接收 UDP 封包與模擬 App 連接 WebSocket。
