# Product Guidelines: V.I.S.O.R.

## Visual Identity & UX Design
- **風格定位：** "Refined Cyberpunk"。保留 Cyberpunk 的高對比與未來感，但導入 Tesla/Apple 的精確感與極簡架構。
- **配色方案：** 深炭黑背景為主，關鍵警示使用螢光橘 (Warning) 與霓虹紅 (Danger)，系統狀態使用科技藍或電子綠。
- **UI 動畫：** 
    - 採用非線性、流暢的過渡動畫 (如 Ease-in-out)。
    - 數據更新需有微型補間動畫，避免數值跳變。
- **資訊優先級：** 介面配置必須確保騎士在 0.5 秒內能理解當前最高優先級的資訊（如：碰撞警示 > 車速 > 導航）。

## Development Principles
- **高效能邊緣運算：**
    - 針對 Raspberry Pi 5 與 Zero 2W 進行極限優化。
    - 優先使用非阻塞式 (Non-blocking) I/O 與多執行緒處理。
    - 影像串流與 AI 推論必須保持穩定幀率 (FPS)。
- **模組化架構：**
    - 各組件（Vision, Sensor, Comm, UI）必須完全解耦。
    - 定義標準化的內部 API 或 JSON 格式進行數據交換。
- **穩定性與容錯：**
    - 網路斷線後必須具備自動重連機制。
    - 哨兵模式需確保在斷電重啟後能自動回復運作。

## Exhibition & Competition Standards (發明展/比賽準則)
- **演示導向功能：** 
    - 內建 `Demo Mode`：支援載入預錄 MP4 影片進行 AI 推論展示，並模擬 GPS/IMU 軌跡。
    - 開發「一鍵部署」腳本，確保在展場能快速重新配置系統。
- **技術文件標準：** 
    - 所有核心邏輯需隨附清晰的 Mermaid 序列圖或架構圖。
    - 程式碼需具備高品質註釋，說明演算法設計的理由。
- **價值主張：** 文件與展示中應持續強調「AI 提升機車騎士生存率」的核心社會價值。
