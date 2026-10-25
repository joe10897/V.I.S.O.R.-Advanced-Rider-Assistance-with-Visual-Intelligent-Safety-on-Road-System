#!/bin/bash
# V.I.S.O.R. Headless Launcher
# 用於實際騎乘或 SSH 遠端執行，不開啟 OpenCV 視窗

# 清理殘留的背景程式 (核心控制器與攝影機)
echo "[V.I.S.O.R.] Cleaning up old tasks..."
pkill -f main_controller.py 2>/dev/null
killall rpicam-vid 2>/dev/null
sleep 2

cd /home/pi5/motorcycle_assist
source venv/bin/activate

# 啟動系統
echo "[V.I.S.O.R.] Launching Headless Mode..."
python3 main_controller.py
