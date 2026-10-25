#!/bin/bash
# =============================================================
#  V.I.S.O.R. — Pi Zero 2W 全新系統初始化腳本
#  適用於：重新燒錄 Raspberry Pi OS Lite (64-bit) 之後
#  執行方式：
#    1. 從 Pi 5 複製此腳本到 Pi Zero:
#       scp scripts/setup_pizero_fresh.sh pi@<PIZERO_IP>:~/
#    2. 登入 Pi Zero 後執行:
#       chmod +x ~/setup_pizero_fresh.sh && sudo bash ~/setup_pizero_fresh.sh
# =============================================================

set -e  # 任何錯誤即停止

# ── 顏色輸出 ──────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

STEP=0
total_steps=7

step() {
    STEP=$((STEP+1))
    echo ""
    echo -e "${CYAN}[${STEP}/${total_steps}] $1${NC}"
    echo "----------------------------------------------"
}

ok() { echo -e "${GREEN}  ✔ $1${NC}"; }
warn() { echo -e "${YELLOW}  ⚠ $1${NC}"; }
fail() { echo -e "${RED}  ✘ $1${NC}"; exit 1; }

# =============================================================
echo ""
echo -e "${CYAN}╔══════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║  V.I.S.O.R. Pi Zero 2W 初始化腳本       ║${NC}"
echo -e "${CYAN}║  HUD Client + OLED + 開機自動啟動        ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════╝${NC}"
echo ""

# ── 確認目前使用者 ─────────────────────────────────────────────
CURRENT_USER=$(logname 2>/dev/null || echo "pi")
HOME_DIR="/home/${CURRENT_USER}"
INSTALL_DIR="${HOME_DIR}/visor_hud"

echo -e "  執行身份：${YELLOW}$(whoami)${NC}"
echo -e "  安裝目標：${YELLOW}${INSTALL_DIR}${NC}"
echo -e "  使用者主目錄：${YELLOW}${HOME_DIR}${NC}"

# =============================================================
step "系統更新與基礎套件安裝"
# =============================================================

apt-get update -y || fail "apt-get update 失敗，請確認網路已連線"
apt-get upgrade -y

# 安裝所有必要的系統套件
apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    python3-pil \
    libffi-dev \
    libssl-dev \
    i2c-tools \
    libi2c-dev \
    fonts-dejavu-core \
    fonts-dejavu-extra \
    git \
    curl \
    || fail "系統套件安裝失敗"

ok "系統套件安裝完成"

# =============================================================
step "啟用 I2C 介面 (OLED SH1106 必須)"
# =============================================================

# 啟用 I2C
if ! grep -q "^dtparam=i2c_arm=on" /boot/firmware/config.txt 2>/dev/null && \
   ! grep -q "^dtparam=i2c_arm=on" /boot/config.txt 2>/dev/null; then
    # 新版 Pi OS 用 /boot/firmware/config.txt
    if [ -f /boot/firmware/config.txt ]; then
        echo "dtparam=i2c_arm=on" >> /boot/firmware/config.txt
        echo "dtparam=i2c_arm_baudrate=400000" >> /boot/firmware/config.txt
    else
        echo "dtparam=i2c_arm=on" >> /boot/config.txt
    fi
    warn "I2C 已加入 config.txt，將在重開機後生效"
else
    ok "I2C 已經啟用"
fi

# 確保 i2c-dev 模組載入
if ! grep -q "i2c-dev" /etc/modules; then
    echo "i2c-dev" >> /etc/modules
fi

# 嘗試立即載入模組
modprobe i2c-dev 2>/dev/null || warn "i2c-dev 模組需要重開機後才能載入"

ok "I2C 設定完成"

# =============================================================
step "建立專案目錄與 Python 虛擬環境"
# =============================================================

# 建立安裝目錄
mkdir -p "${INSTALL_DIR}/hud"
mkdir -p "${INSTALL_DIR}/logs"
chown -R ${CURRENT_USER}:${CURRENT_USER} "${INSTALL_DIR}"

# 建立 Python 虛擬環境
if [ ! -d "${INSTALL_DIR}/venv" ]; then
    sudo -u ${CURRENT_USER} python3 -m venv "${INSTALL_DIR}/venv"
    ok "虛擬環境建立完成"
else
    ok "虛擬環境已存在，跳過建立"
fi

# =============================================================
step "安裝 Python 套件 (luma.oled, Pillow)"
# =============================================================

VENV_PIP="${INSTALL_DIR}/venv/bin/pip"

sudo -u ${CURRENT_USER} ${VENV_PIP} install --upgrade pip
sudo -u ${CURRENT_USER} ${VENV_PIP} install \
    "luma.oled>=3.13.0" \
    "Pillow>=10.0.0" \
    || fail "Python 套件安裝失敗"

ok "luma.oled 與 Pillow 安裝完成"

# 驗證安裝
VENV_PYTHON="${INSTALL_DIR}/venv/bin/python3"
if sudo -u ${CURRENT_USER} ${VENV_PYTHON} -c "from luma.oled.device import sh1106; print('luma.oled OK')" 2>/dev/null; then
    ok "luma.oled 匯入測試通過"
else
    warn "luma.oled 匯入測試失敗，可能需要重開機後 I2C 才能正常運作"
fi

# =============================================================
step "部署 hud_client.py"
# =============================================================

# 從此腳本所在目錄找 hud_client.py
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
HUD_SOURCE=""

# 搜尋 hud_client.py 的可能位置
for search_path in \
    "${SCRIPT_DIR}/../hud/hud_client.py" \
    "${HOME_DIR}/hud_client.py" \
    "/tmp/hud_client.py"; do
    if [ -f "${search_path}" ]; then
        HUD_SOURCE="${search_path}"
        break
    fi
done

if [ -n "${HUD_SOURCE}" ]; then
    cp "${HUD_SOURCE}" "${INSTALL_DIR}/hud/hud_client.py"
    chown ${CURRENT_USER}:${CURRENT_USER} "${INSTALL_DIR}/hud/hud_client.py"
    ok "hud_client.py 複製完成：${HUD_SOURCE}"
else
    warn "找不到 hud_client.py，請手動複製到 ${INSTALL_DIR}/hud/hud_client.py"
    warn "可從 Pi 5 執行：scp /path/to/hud/hud_client.py ${CURRENT_USER}@$(hostname -I | awk '{print $1}'):${INSTALL_DIR}/hud/"
    # 建立一個簡易的測試版 hud_client.py 確認 OLED 是否正常
    cat > "${INSTALL_DIR}/hud/hud_client.py" << 'PLACEHOLDER'
#!/usr/bin/env python3
# 這是暫時佔位版本，請從 Pi 5 複製正式的 hud_client.py
import socket, json, time
from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import sh1106

serial = i2c(port=1, address=0x3C)
device = sh1106(serial, width=128, height=64)
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(('0.0.0.0', 5005))
sock.settimeout(5.0)
print("HUD PLACEHOLDER: Listening on UDP :5005...")
last = 0
while True:
    with canvas(device) as draw:
        if time.time() - last > 5:
            draw.text((10, 20), "SIGNAL LOST", fill="white")
            draw.text((5, 40), "Waiting Pi5...", fill="white")
        else:
            draw.text((20, 25), "CONNECTED", fill="white")
    try:
        data, _ = sock.recvfrom(4096)
        last = time.time()
        print("Received:", data[:50])
    except socket.timeout:
        pass
PLACEHOLDER
    chown ${CURRENT_USER}:${CURRENT_USER} "${INSTALL_DIR}/hud/hud_client.py"
    warn "已部署佔位版 hud_client.py，請盡快替換為正式版本"
fi

# =============================================================
step "建立 systemd 開機自動啟動服務"
# =============================================================

SERVICE_FILE="/etc/systemd/system/visor-hud.service"

cat > "${SERVICE_FILE}" << EOF
[Unit]
Description=V.I.S.O.R. HUD Client - Pi Zero 2W OLED Display
Documentation=https://github.com/joe10897/Visor
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${CURRENT_USER}
WorkingDirectory=${INSTALL_DIR}
ExecStart=${INSTALL_DIR}/venv/bin/python3 ${INSTALL_DIR}/hud/hud_client.py
StandardOutput=append:${INSTALL_DIR}/logs/hud.log
StandardError=append:${INSTALL_DIR}/logs/hud_error.log
Restart=always
RestartSec=5
# 等待網路完全就緒後再啟動 (避免 Wi-Fi 還沒連好就跑)
ExecStartPre=/bin/sleep 8
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONDONTWRITEBYTECODE=1

[Install]
WantedBy=multi-user.target
EOF

# 重新載入並啟用服務
systemctl daemon-reload
systemctl enable visor-hud.service

ok "systemd 服務設定完成 (visor-hud.service)"

# =============================================================
step "OLED 連線快速診斷"
# =============================================================

echo "  正在掃描 I2C 裝置..."
if command -v i2cdetect &> /dev/null; then
    # 嘗試 I2C bus 1 (Pi Zero 預設)
    I2C_RESULT=$(i2cdetect -y 1 2>/dev/null || echo "ERROR")
    if echo "${I2C_RESULT}" | grep -q "3c\|3C"; then
        ok "OLED 裝置偵測到！I2C 位址: 0x3C"
    elif echo "${I2C_RESULT}" | grep -q "ERROR"; then
        warn "I2C 尚未就緒，請重開機後再執行: i2cdetect -y 1"
    else
        warn "I2C bus 正常但未偵測到 OLED，請確認接線："
        warn "  SDA → GPIO2 (Pin 3)"
        warn "  SCL → GPIO3 (Pin 5)"
        warn "  VCC → 3.3V (Pin 1)"
        warn "  GND → GND  (Pin 6)"
        echo ""
        echo "${I2C_RESULT}"
    fi
else
    warn "i2cdetect 未安裝，重開機後執行: sudo i2cdetect -y 1"
fi

# =============================================================
# ── 完成摘要 ──────────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  ✅  初始化完成！                         ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
echo ""
echo "  安裝路徑：${INSTALL_DIR}"
echo "  服務狀態：sudo systemctl status visor-hud"
echo "  即時日誌：sudo journalctl -u visor-hud -f"
echo "  OLED診斷：sudo i2cdetect -y 1"
echo ""
echo -e "${YELLOW}  下一步：${NC}"
echo "  1. 執行 sudo reboot 重開機"
echo "  2. 重開機後確認：sudo systemctl status visor-hud"
echo "  3. 在 Pi 5 執行 ping <PIZERO_IP> 確認網路連線"
echo "  4. 觀察 OLED 是否顯示開機畫面"
echo ""
echo -e "${YELLOW}  若 hud_client.py 還是佔位版，請在 Pi 5 上執行：${NC}"
echo "  scp hud/hud_client.py ${CURRENT_USER}@<PIZERO_IP>:${INSTALL_DIR}/hud/"
echo "  sudo systemctl restart visor-hud"
echo ""
