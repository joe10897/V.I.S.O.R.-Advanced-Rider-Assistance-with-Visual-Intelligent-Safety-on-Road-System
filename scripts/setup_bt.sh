#!/bin/bash
# V.I.S.O.R. Bluetooth Initialization Script

echo "[BT] Powering on and setting discoverable..."
sudo bluetoothctl power on
sudo bluetoothctl discoverable on
sudo bluetoothctl pairable on

# 掛載 Serial Port Profile (SPP)
echo "[BT] Adding Serial Port Profile..."
sudo sdptool add SP

# 確保權限
sudo chmod 666 /var/run/sdp

echo "[BT] Bluetooth environment ready."
