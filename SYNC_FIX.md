# V.I.S.O.R. 同步修復部署說明 (SYNC FIX)

> 本文件說明如何將 Pi 5 與 Pi Zero 2W 的「連線同步 + App/HUD 設定」修復部署到實機。
> 適用情境：實體網線對接、學校公共 Wi-Fi、Pi 5 熱點 (AP) 三種連線模式。

---

## 1. 修復內容摘要

| 檔案 | 變更 | 解決的問題 |
|------|------|-----------|
| `hud/hud_client.py` | 心跳改為**多路單播 + 通用廣播** | 學校 Wi-Fi 封鎖廣播、實體網線網段不符時，HUD 仍可主動找到 Pi 5 |
| `config.json` | `broadcast_ip` 改為 `255.255.255.255` | 網段無關的通用廣播，實體網線/熱點都能送達 |
| `tests/test_hud_heartbeat.py` | 修正 `get_last_heartbeat()` 3 值 unpack bug | 測試正確性 |

### 為什麼有效？
- 路由器與作業系統**不會阻擋單播 (Unicast) 封包**
- HUD 主動向 `pi5.local` (mDNS)、`192.168.4.1` (AP 閘道)、`255.255.255.255` (通用廣播) 發送心跳
- Pi 5 收到心跳後得知 HUD 真實 IP → 立刻切換為**單播**傳輸
- 之後所有 `hud_config`（亮度/時間開關）都能 100% 即時同步

---

## 2. 部署步驟

### 2.1 前置準備
確認本機 (Windows) 與 Pi 5 已連線（實體網線或同網段 Wi-Fi），可執行：
```powershell
ssh pi5@pi5.local
```

### 2.2 Pi 5 端部署
```powershell
# 從 Windows 本機同步
scp ./main_controller.py pi5@pi5.local:/home/pi5/motorcycle_assist/
scp ./config.json pi5@pi5.local:/home/pi5/motorcycle_assist/
scp ./visor_bt_agent.py pi5@pi5.local:/home/pi5/motorcycle_assist/scripts/
scp -r ./YOLOv26_DEMO pi5@pi5.local:/home/pi5/motorcycle_assist/
```

SSH 進入 Pi 5 重啟核心服務：
```bash
cd /home/pi5/motorcycle_assist
source venv/bin/activate
sudo systemctl restart visor-core
journalctl -u visor-core -n 30   # 檢查啟動日誌
```

### 2.3 Pi Zero 2W 端部署
先確認 Pi Zero 的帳號與路徑（舊版 service 使用 `/home/pi/`，請依實際調整）：
```powershell
scp ./hud/hud_client.py pizero@<pizero-ip>:/home/pi/motorcycle_assist/hud/
```

SSH 進入 Pi Zero 重啟 HUD 服務：
```bash
sudo systemctl restart visor-hud
journalctl -u visor-hud -n 30    # 檢查啟動日誌
```

> 若 HUD service 路徑不符，請檢查 `scripts/visor-hud.service` 的 `ExecStart` 是否指向正確使用者目錄，並執行 `sudo systemctl daemon-reload`。

---

## 3. 驗證清單

部署完成後，依序驗證：

- [ ] **HUD 上電**：OLED 顯示 `V.I.S.O.R. INITIALIZING` 後進入主畫面
- [ ] **秒連**：HUD 出現速度/傾角/CPU 溫度（代表已收到 Pi 5 資料）
- [ ] **App 連線**：開啟 V.I.S.O.R. App → Wi-Fi 連線成功 (Neural Link: Wi-Fi Connected)
- [ ] **設定同步**：App 調整 HUD 亮度滑桿 → Pi Zero OLED 亮度即時改變
- [ ] **開關同步**：App 關閉「時間顯示」→ HUD 頂欄時間消失
- [ ] **斷線恢復**：關閉 Pi Zero → Pi 5 顯示 HUD offline → 重新開機 → 自動恢復連線

### 三種連線模式測試
| 模式 | 測試方式 | 預期結果 |
|------|---------|---------|
| 熱點 AP | 手機/電腦連 Pi 5 Wi-Fi | 秒連、設定即時同步 |
| 實體網線 | 網線對接 Pi 5 ↔ Pi Zero | 秒連、設定即時同步 |
| 學校/家用 Wi-Fi | 兩台連同一路由器 | 秒連、設定即時同步 |

---

## 4. 故障排除

| 症狀 | 可能原因 | 解法 |
|------|---------|------|
| HUD 顯示 `SIGNAL LOST` | UDP 封包未送達 | 檢查 `config.json` `broadcast_ip` 是否為 `255.255.255.255` |
| Pi 5 顯示 HUD offline | HUD 心跳未送達 | 確認 Pi Zero 上 `hud_client.py` 已更新（含 `pi5.local` 心跳） |
| App 連不上 | WebSocket 埠被擋 | 確認 Pi 5 防火牆開放 `8765` |
| 設定改了沒反應 | HUD 沒收到 `hud_config` | 確認 Pi 5 `visor-core` 已重啟、`config.json` 已更新 |

### 手動測試同步
在本機快速驗證兩端是否互通：
```powershell
# 本機發送測試廣播到 Pi Zero
python -c "
import socket, json
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
s.sendto(json.dumps({'test': True, 'hud_config': {'brightness': 255}}).encode(), ('255.255.255.255', 5005))
print('Broadcast sent')
"
```

---

## 5. 相關檔案位置

```
motorcycle_assist/
├── hud/
│   └── hud_client.py              # HUD 客戶端 (心跳多路單播修復)
├── config.json                    # broadcast_ip = 255.255.255.255
├── main_controller.py             # 主控制器 (已整合 VisorCore)
├── visor_bt_agent.py              # 藍牙自動配對代理人
├── scripts/
│   └── visor-hud.service          # HUD systemd 服務
├── tests/
│   ├── test_hud_e2e_integration.py  # E2E 同步測試
│   └── test_hud_heartbeat.py        # 心跳測試 (已修 unpack bug)
└── YOLOv26_DEMO/                  # 新版 AI 管線 (YOLOv26n + LSTR CULane)
```
