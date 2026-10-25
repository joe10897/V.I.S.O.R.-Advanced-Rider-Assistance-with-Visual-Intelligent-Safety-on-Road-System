# Implementation Plan: System Monitoring

## Phase 1: Backend Updates
- [x] **Task 1: Update `MainController` Payload**
    -   使用 `psutil` 獲取真實 CPU/RAM 指標。
    -   實現 `get_cpu_temp()` 獲取 Pi 5 溫度。
    -   將 `system` 字典加入廣播數據。

## Phase 2: Frontend Updates
- [x] **Task 2: Implement Notification Component**
    -   優化 `ToastNotification` 組件與 React 狀態管理。
- [x] **Task 3: Update Header UI**
    -   實現 CORE (Pi 5) 與 HUD (Pi Zero) 獨立狀態燈。
    -   連接指標到 WebSocket/Bluetooth 即時數據。

## Phase 3: Verification
- [x] **Task 4: Simulation Test**
    -   驗證斷線時燈號變紅。
    -   驗證溫度與負載數據正確顯示。
