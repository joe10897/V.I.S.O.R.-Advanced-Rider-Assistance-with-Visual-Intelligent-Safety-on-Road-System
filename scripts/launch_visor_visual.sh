#!/bin/bash
# V.I.S.O.R. Desktop Launcher (Visual Mode)
# 用於 Pi 5 接螢幕時的展示模式

# 清理殘留的背景程式
killall rpicam-vid 2>/dev/null
sleep 0.5

cd /home/pi5/motorcycle_assist
source venv/bin/activate

# 啟動系統（含 OpenCV 視窗）
python3 main_controller.py --visual
echo "執行結束 (Exit Code: $?)"
read -p "請按 [Enter] 關閉此視窗..."
