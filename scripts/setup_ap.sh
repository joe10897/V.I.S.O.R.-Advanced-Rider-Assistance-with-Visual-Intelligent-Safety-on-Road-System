#!/bin/bash
# V.I.S.O.R. Network Toggle Script
SSID="VISOR_System"
PASS="12345678"

if [ "$1" == "ap" ]; then
    echo "Switching to Hotspot Mode..."
    sudo nmcli con add type wifi ifname wlan0 mode ap con-name VISOR_AP ssid $SSID
    sudo nmcli con modify VISOR_AP 802-11-wireless.band bg
    sudo nmcli con modify VISOR_AP 802-11-wireless.channel 6
    sudo nmcli con modify VISOR_AP ipv4.method shared
    sudo nmcli con modify VISOR_AP ipv4.addresses 192.168.4.1/24
    sudo nmcli con modify VISOR_AP wifi-sec.key-mgmt wpa-psk
    sudo nmcli con modify VISOR_AP wifi-sec.psk $PASS
    sudo nmcli con up VISOR_AP
    echo "AP Started: $SSID / $PASS"
    echo "Pi 5 IP is now: 192.168.4.1"
elif [ "$1" == "client" ]; then
    echo "Switching to Client Mode..."
    sudo nmcli con down VISOR_AP
    sudo nmcli con delete VISOR_AP
    echo "Restored. Reconnect to your home Wi-Fi."
else
    echo "Usage: ./setup_ap.sh [ap|client]"
fi
