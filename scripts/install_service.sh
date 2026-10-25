#!/bin/bash
# =============================================================
#  V.I.S.O.R. Pi 5 開機自動啟動服務安裝腳本 (systemd)
# =============================================================

echo "============================================================"
echo "  [V.I.S.O.R.] 正在安裝 Pi 5 開機自啟動服務 (visor.service)..."
echo "============================================================"

# 停用舊的或衝突的 visor-core.service
sudo systemctl stop visor-core.service 2>/dev/null || true
sudo systemctl disable visor-core.service 2>/dev/null || true

SERVICE_PATH="/etc/systemd/system/visor.service"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

sudo cp "$SCRIPT_DIR/visor.service" "$SERVICE_PATH"
sudo systemctl daemon-reload
sudo systemctl enable visor.service
sudo systemctl restart visor.service

echo "============================================================"
echo "  [SUCCESS] V.I.S.O.R. 開機自啟動服務已成功啟用！"
echo "  服務狀態查詢指令: sudo systemctl status visor.service"
echo "  日誌即時檢視指令: sudo journalctl -u visor.service -f"
echo "============================================================"
