#!/usr/bin/env python3
# ==============================================================================
#  V.I.S.O.R. OLED 硬體單獨一次性檢測與點亮腳本 (支援 0.96" 與 1.3" I2C)
# ==============================================================================

import sys
import time
import os
import subprocess

# 檢查是否有 root 權限 (部分 I2C 訪問需要)
is_root = os.geteuid() == 0 if hasattr(os, 'geteuid') else False

print("=" * 65)
print("  🔍 V.I.S.O.R. OLED 硬體通訊與點亮診斷程式 (0.96\" / 1.3\")")
print("=" * 65)

# 1. 檢查 I2C 匯流排狀態
print("\n[*] 步驟 1/3: 掃描 I2C-1 匯流排...")
detected_addrs = []
try:
    res = subprocess.run(["i2cdetect", "-y", "1"], capture_output=True, text=True, errors='replace')
    print(res.stdout)
    for line in res.stdout.splitlines()[1:]:
        parts = line.split(":")
        if len(parts) == 2:
            for item in parts[1].split():
                if item != "--" and item != "":
                    try:
                        addr = int(item, 16)
                        detected_addrs.append(addr)
                    except ValueError:
                        pass
except Exception as e:
    print(f"[-] 執行 i2cdetect 失敗: {e}")

if not detected_addrs:
    print("\n" + "!" * 65)
    print("❌ 警告：I2C 匯流排上未掃描到任何裝置 (全為 --)！")
    print("!" * 65)
    print("\n⚠️ 【極高機率原因：0.96\" 與 1.3\" 的針腳順序顛倒！】")
    print("   市售 OLED 模組有兩種常見的防呆陷阱：")
    print("   • 版本 A (多數 0.96\"): [Pin 1: GND] [Pin 2: VCC] [Pin 3: SCL] [Pin 4: SDA]")
    print("   • 版本 B (多數 1.3\" ): [Pin 1: VCC] [Pin 2: GND] [Pin 3: SCL] [Pin 4: SDA]")
    print("   👉 請立刻看一眼 0.96\" OLED 背面/正面的絲印標籤，GND 和 VCC 是否反了！")
    print("\n📌 樹莓派標準 40-Pin GPIO 接線對照表：")
    print("   • OLED VCC  ---> 樹莓派 Pin 1 (3.3V) 或 Pin 2 (5V)")
    print("   • OLED GND  ---> 樹莓派 Pin 6 或 Pin 9 (GND)")
    print("   • OLED SCL  ---> 樹莓派 Pin 5 (GPIO 3 / SCL)")
    print("   • OLED SDA  ---> 樹莓派 Pin 3 (GPIO 2 / SDA)")
    print("=" * 65)
    sys.exit(1)

print(f"[+] 成功於 I2C 匯流排找到裝置地址: {[hex(a) for a in detected_addrs]}")

# 2. 嘗試初始化 OLED 驅動
print("\n[*] 步驟 2/3: 嘗試載入 OLED 驅動並點亮螢幕...")

device = None
dev_name = None
used_addr = None

try:
    from luma.core.interface.serial import i2c
    from luma.oled.device import ssd1306, sh1106
    from PIL import Image, ImageDraw, ImageFont
except ImportError as e:
    print(f"[-] 缺少必要函式庫: {e}")
    print("    請確認在 venv 環境下執行: ./venv/bin/python3 scripts/test_oled_hardware.py")
    sys.exit(1)

# 候選清單：0.96" 通常是 ssd1306，1.3" 通常是 sh1106
candidates = [
    ("SSD1306 (0.96\" 標準晶片)", ssd1306, 0x3C),
    ("SSD1306 (0.96\" 次要位址)", ssd1306, 0x3D),
    ("SH1106  (1.3\"  標準晶片)", sh1106,  0x3C),
    ("SH1106  (1.3\"  次要位址)", sh1106,  0x3D),
]

for name, driver_cls, addr in candidates:
    if addr in detected_addrs or len(detected_addrs) == 0:
        try:
            print(f"    - 嘗試 {name} @ 0x{addr:02X}...", end=" ", flush=True)
            serial = i2c(port=1, address=addr)
            dev = driver_cls(serial, width=128, height=64, rotate=0)
            dev.contrast(255)  # 最大亮度
            device = dev
            dev_name = name
            used_addr = addr
            print("【成功握手！】")
            break
        except Exception as e:
            print(f"失敗 ({e})")

if not device:
    print("\n[-] 無法以任何已知驅動成功驅動 OLED，請確認螢幕晶片型號。")
    sys.exit(1)

# 3. 執行視覺點亮測試 (全白頻閃 -> 畫框 -> 倒數)
print("\n[*] 步驟 3/3: 正在向螢幕發送測試圖形 (全亮測試 -> 診斷文字)...")

try:
    # 階段 1: 全屏點亮 (白色全滿) 測試壞點
    print("    >> 階段 1: 全屏白光測試 (持續 1.5 秒)...")
    full_white = Image.new("1", (128, 64), 255)
    device.display(full_white)
    time.sleep(1.5)

    # 階段 2: 繪製 V.I.S.O.R. 診斷畫面與動態倒數
    print("    >> 階段 2: 繪製 V.I.S.O.R. 幾何邊框與診斷文字...")
    for remaining in range(5, 0, -1):
        img = Image.new("1", (128, 64), 0)
        draw = ImageDraw.Draw(img)

        # 外框與幾何線條
        draw.rectangle((0, 0, 127, 63), outline="white")
        draw.rectangle((2, 2, 125, 12), fill="white")
        draw.text((12, 2), "V.I.S.O.R. HUD TEST", fill="black")

        # 核心規格
        draw.text((6, 18), f"STATUS: HARDWARE OK", fill="white")
        draw.text((6, 30), f"CHIP:   {dev_name.split()[0]}", fill="white")
        draw.text((6, 42), f"ADDR:   0x{used_addr:02X} (128x64)", fill="white")

        # 動態倒數提示
        draw.text((6, 52), f"CLOSING IN {remaining}s...", fill="white")
        draw.line((100, 56, 120, 56), fill="white")

        device.display(img)
        time.sleep(1.0)

    print("\n" + "=" * 65)
    print(f"  🎉 恭喜！OLED 螢幕點亮測試 100% 成功！")
    print(f"  • 識別晶片: {dev_name}")
    print(f"  • I2C 地址: 0x{used_addr:02X}")
    print("=" * 65)

    # 清空螢幕收尾
    device.clear()

except KeyboardInterrupt:
    print("\n[INFO] 使用者手動中斷。")
    if device:
        device.clear()
except Exception as e:
    print(f"\n[-] 繪圖時發生異常: {e}")
