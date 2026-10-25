# Implementation Plan: HUD & OLED Integration

## Phase 1: Communication & App
- [x] **Task 1: Update App HUD Settings**
    -   APP 端支援 `set_hud_config` 指令。
    -   實現藍牙 SPP 通訊作為主要連線方案。
- [x] **Task 2: Core Controller Support**
    -   `MainController` 支援藍牙與 UDP 同步廣播。
    -   修正藍牙伺服器語法與依賴問題。

## Phase 2: Pi Zero Client Development
- [x] **Task 3: Create `hud/hud_client.py`**
    -   實現 UDP 接收器。
    -   實現 SSD1306 渲染邏輯。
    -   設計時速與警告介面。
- [x] **Task 4: Systemd Service File**
    -   建立自動啟動服務。

## Phase 3: Hardware Verification [checkpoint: 0a44553]
- [x] **Task 5: End-to-End Test** (580646c)
    -   驗證 Pi 5 偵測到威脅時，Pi Zero OLED 即時顯示。
