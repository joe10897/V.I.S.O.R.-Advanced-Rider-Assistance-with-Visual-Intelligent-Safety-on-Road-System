#!/bin/bash
# =============================================================
#  V.I.S.O.R. HUD Deployment Tool (Pi Zero 2W + 1.3" OLED I2C)
# =============================================================
set -e

echo "-----------------------------------------------"
echo "  V.I.S.O.R. HUD Deployment Tool (Pi Zero 2W)"
echo "  Target: 1.3\" OLED I2C (SH1106 / SSD1306 128x64)"
echo "-----------------------------------------------"

# Detect current user and home directory
CURRENT_USER=$(logname 2>/dev/null || whoami)
HOME_DIR=$(eval echo "~${CURRENT_USER}")
INSTALL_DIR="${HOME_DIR}/motorcycle_assist"

echo "  Target User: $CURRENT_USER"
echo "  Target Path: $INSTALL_DIR"

# 1. Update and Install System Dependencies
echo "[1/4] Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y \
    python3-pip \
    python3-venv \
    python3-dev \
    libffi-dev \
    libssl-dev \
    i2c-tools \
    libi2c-dev \
    python3-pil \
    fonts-dejavu-core \
    fonts-dejavu-extra

# 2. Setup I2C (Required for SH1106/SSD1306)
echo "[2/4] Enabling I2C and setting 400kHz fast mode..."
sudo raspi-config nonint do_i2c 0

# Set 400kHz baudrate for smooth 20+ FPS rendering
CONFIG_TXT="/boot/firmware/config.txt"
if [ ! -f "$CONFIG_TXT" ]; then
    CONFIG_TXT="/boot/config.txt"
fi

if ! grep -q "dtparam=i2c_arm_baudrate=400000" "$CONFIG_TXT"; then
    echo "dtparam=i2c_arm_baudrate=400000" | sudo tee -a "$CONFIG_TXT"
fi

# Ensure i2c-dev is loaded
if ! grep -q "i2c-dev" /etc/modules 2>/dev/null; then
    echo "i2c-dev" | sudo tee -a /etc/modules
fi
sudo modprobe i2c-dev 2>/dev/null || true

# 3. Setup Virtual Environment
echo "[3/4] Setting up Python virtual environment..."
mkdir -p "$INSTALL_DIR/hud" "$INSTALL_DIR/logs"
cd "$INSTALL_DIR"

if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

source venv/bin/activate
pip install --upgrade pip
pip install "luma.oled>=3.13.0" "Pillow>=10.0.0"

# 4. Setup Systemd Service
echo "[4/4] Configuring systemd service..."
SERVICE_FILE="/etc/systemd/system/visor-hud.service"
sudo bash -c "cat > $SERVICE_FILE" <<EOF
[Unit]
Description=V.I.S.O.R. HUD Client (Pi Zero 2W + 1.3" OLED)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/python3 $INSTALL_DIR/hud/hud_client.py
StandardOutput=inherit
StandardError=inherit
Restart=always
RestartSec=3
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONDONTWRITEBYTECODE=1

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable visor-hud.service
sudo systemctl restart visor-hud.service

echo "-----------------------------------------------"
echo "  DEPLOYMENT COMPLETE!"
echo "  User:   $CURRENT_USER"
echo "  Status: sudo systemctl status visor-hud"
echo "  Logs:   sudo journalctl -u visor-hud -f"
echo "  I2C:    sudo i2cdetect -y 1"
echo "-----------------------------------------------"
