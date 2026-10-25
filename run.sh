#!/bin/bash
# =============================================================
#  V.I.S.O.R. Pi 5 核心啟動腳本
#  (雙 USB 2.0 Sony IMX662 [前 120° / 後 173°] + 360 雷達 + SPP 藍牙)
# =============================================================

echo "============================================================"
echo "  [V.I.S.O.R.] 正在清理佔用相機與通訊埠 (8765/5005/5006)..."
echo "============================================================"

# 1. 暫停衝突背景服務 (如果不是由 systemd 服務啟動)
if [ -z "$INVOCATION_ID" ] && [ -z "$JOURNAL_STREAM" ]; then
    sudo systemctl stop visor.service visor-core.service 2>/dev/null || true
fi

# 2. 強制釋放網路埠與相機設備節點
sudo fuser -k -9 8765/tcp 2>/dev/null || true
sudo fuser -k -9 5005/udp 2>/dev/null || true
sudo fuser -k -9 5006/udp 2>/dev/null || true
sudo fuser -k -9 /dev/video0 /dev/video1 /dev/video2 /dev/video3 2>/dev/null || true
pkill -9 -f rpicam 2>/dev/null || true
pkill -9 -f libcamera 2>/dev/null || true

# 強制清理所有殘留的舊 main_controller 程序
pgrep -f "python3.*main_controller" | grep -v "$$" | xargs -r sudo kill -9 2>/dev/null || true
sleep 0.8

# 3. 自動啟用 Python 虛擬環境
cd "$(dirname "$0")"
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
elif [ -f "$HOME/.venv/bin/activate" ]; then
    source "$HOME/.venv/bin/activate"
fi

# 4. 硬體優化：預先設定 Sony IMX662 USB 鏡頭為高畫質 30 FPS MJPG 模式與關閉低光降速
for vdev in /dev/video0 /dev/video2; do
    if [ -e "$vdev" ]; then
        v4l2-ctl -d "$vdev" --set-fmt-video=width=640,height=480,pixelformat=MJPG 2>/dev/null || true
        v4l2-ctl -d "$vdev" --set-parm=30 2>/dev/null || true
        v4l2-ctl -d "$vdev" --set-ctrl=exposure_auto_priority=0 2>/dev/null || true
    fi
done

# 5. 確保 Pi 5 藍牙硬體開啟、可發現並註冊序列埠 (SPP)
sudo rfkill unblock bluetooth 2>/dev/null || true
bluetoothctl power on 2>/dev/null || true
bluetoothctl discoverable on 2>/dev/null || true
bluetoothctl pairable on 2>/dev/null || true
sudo sdptool add SP 2>/dev/null || true

# 啟動藍牙免螢幕自動配對代理人 (Headless NoInputNoOutput Auto-Pairing)
pkill -f visor_bt_agent.py 2>/dev/null || true
if [ -f "visor_bt_agent.py" ]; then
    python3 visor_bt_agent.py >/dev/null 2>&1 &
    echo "  [V.I.S.O.R.] 藍牙免螢幕自動配對代理人已啟動"
fi

echo "============================================================"
echo "  [V.I.S.O.R.] 藍牙 SPP 序列埠已就緒 (名稱: VISOR_Core)"
echo "  [V.I.S.O.R.] 雙 USB IMX662 鏡頭 (前 /dev/video0, 後 /dev/video2) 已就緒"
echo "  [V.I.S.O.R.] 啟動核心主控制器 (雙向 ADAS + 360 雷達)..."
echo "============================================================"

# 6. 捕捉 Ctrl+C / TERM 安全清理
trap 'pkill -9 -f rpicam 2>/dev/null; pkill -f visor_bt_agent.py 2>/dev/null; sudo fuser -k -9 /dev/video0 /dev/video2 2>/dev/null; exit 0' INT TERM

exec python3 -u main_controller.py "$@"
