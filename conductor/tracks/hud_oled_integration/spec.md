# Specification: HUD & OLED Integration

## Goal
Enable the App to control HUD display settings and implement the Pi Zero client that drives the OLED display.

## Components

### 1. HUD Protocol (UDP)
Extend the existing UDP payload to include HUD configuration:
```json
{
  "timestamp": 123456789,
  "speed": 60,
  "tilt": 5,
  "warning": {...},
  "hud_config": {
    "brightness": 128,      // 0-255
    "layout": "default",    // "standard", "minimal", "sport"
    "show_time": true
  }
}
```

### 2. Pi 5 Core (`main_controller.py`)
-   Store a persistent `hud_config` object.
-   Update `hud_config` when receiving WebSocket commands from the App.
-   Include `hud_config` in every UDP broadcast to the Pi Zero.

### 3. Pi Zero Client (`hud/hud_client.py`)
-   **Hardware**: SSD1306 OLED (I2C).
-   **Service**: Auto-start on boot via Systemd.
-   **Logic**:
    -   Listen for UDP on Port 5005.
    -   Render speed, tilt, and warnings to OLED.
    -   Apply brightness and layout settings dynamically.

### 4. App (`app.html`)
-   Connect HUD Settings toggles to the WebSocket command system.

## Success Criteria
1.  Pi Zero displays "V.I.S.O.R. Ready" on boot.
2.  App changes layout, and OLED updates immediately.
3.  Speed data from Core is rendered in real-time on OLED.
