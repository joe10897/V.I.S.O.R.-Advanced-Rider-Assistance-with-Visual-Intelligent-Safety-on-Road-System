#!/bin/bash
# V.I.S.O.R. Pi 5 Core Deployment Script
# Optimized for Raspberry Pi OS (64-bit)

set -e

echo "-----------------------------------------------"
echo "  V.I.S.O.R. Core Deployment Tool (Pi 5)"
echo "-----------------------------------------------"

# 1. Update and Install System Dependencies
echo "[1/5] Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y 
    python3-pip 
    python3-venv 
    libgl1-mesa-glx 
    libglib2.0-0 
    v4l-utils 
    v4l2loopback-dkms 
    bluez 
    python3-psutil

# 2. Setup Virtual Environment
echo "[2/5] Setting up Python virtual environment..."
cd ~/motorcycle_assist
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 3. Setup Project Folders
echo "[3/5] Initializing directories..."
mkdir -p events sample_videos

# 4. Setup Systemd Service
echo "[4/5] Configuring systemd service..."
SERVICE_FILE="/etc/systemd/system/visor-core.service"
sudo bash -c "cat > $SERVICE_FILE" <<EOF
[Unit]
Description=V.I.S.O.R. Main Controller (Pi 5)
After=network.target

[Service]
ExecStart=/home/pi5/motorcycle_assist/venv/bin/python3 /home/pi5/motorcycle_assist/main_controller.py
WorkingDirectory=/home/pi5/motorcycle_assist
StandardOutput=inherit
StandardError=inherit
Restart=always
User=pi5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable visor-core.service

# 5. Network Optimization (Optional but recommended for AP)
echo "[5/5] Checking Network AP Status..."
if [ -f "./scripts/setup_ap.sh" ]; then
    echo "Running setup_ap.sh to ensure VISOR_AP is configured..."
    chmod +x ./scripts/setup_ap.sh
    # We don't force AP on here to avoid kicking the user off SSH if they aren't on AP yet
    echo "Network script ready. Run './scripts/setup_ap.sh ap' to switch to Hotspot Mode."
fi

echo "-----------------------------------------------"
echo "  DEPLOYMENT COMPLETE!"
echo "  Start Core with: sudo systemctl start visor-core"
echo "  Check Logs with: journalctl -u visor-core -f"
echo "-----------------------------------------------"
