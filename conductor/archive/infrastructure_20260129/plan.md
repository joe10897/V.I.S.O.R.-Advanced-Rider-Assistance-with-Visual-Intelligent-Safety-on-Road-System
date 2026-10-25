# Implementation Plan: Core Communication Infrastructure

## Phase 1: Environment & System Configuration [x]
建立 Raspberry Pi 5 的基礎運作環境設定腳本。

- [x] Task: 建立 `setup_ap.sh` 腳本 (no git)
    - [x] Sub-task: 編寫 NetworkManager (nmcli) 設定指令，建立 `VISOR_Net` 熱點。
    - [x] Sub-task: 設定固定 IP `192.168.4.1`。
- [x] Task: 更新 `requirements.txt` (no git)
    - [x] Sub-task: 加入 `websockets` 與 `asyncio` (標準庫確認) 等依賴。

## Phase 2: Communication Modules Implementation [x]
實作 Python 通訊類別，確保模組化與非阻塞特性。

- [x] Task: 實作 `communication/udp_broadcaster.py` (no git)
    - [x] Sub-task: 定義 `UdpBroadcaster` 類別。
    - [x] Sub-task: 實作 `send_data(data: dict)` 方法，包含 JSON 序列化與例外處理。
    - [x] Sub-task: 撰寫單元測試 `tests/test_udp.py` 驗證封包發送。
- [x] Task: 實作 `communication/websocket_server.py` (no git)
    - [x] Sub-task: 定義 `VisorWebSocketServer` 類別。
    - [x] Sub-task: 實作 `broadcast(message)` 與 `handler` 方法。
    - [x] Sub-task: 使用 `asyncio` 整合 WebSocket 服務。

## Phase 3: Main Controller & Integration [x]
重構入口程式，整合通訊模組。

- [x] Task: 建立 `main_controller.py` (no git)
    - [x] Sub-task: 建立非同步主迴圈 (Async Event Loop)。
    - [x] Sub-task: 整合 `UdpBroadcaster` 與 `VisorWebSocketServer` 實例。
    - [x] Sub-task: 實作 Dummy Data Generator，模擬感測器數據以測試通訊流。
- [x] Task: 建立驗證工具 `tools/test_clients.py` (no git)
    - [x] Sub-task: 實作一個簡易 UDP Listener (模擬 HUD)。
    - [x] Sub-task: 實作一個簡易 WebSocket Client (模擬 App)。
