# Specification: Configuration Management

## Goal
Centralize all hardcoded parameters (IPs, Ports, Thresholds, Model Paths) into a single `config.json` file.

## Components

### 1. Config File (`config.json`)
-   **Structure**:
    ```json
    {
      "network": {
        "broadcast_ip": "192.168.4.255",
        "udp_port": 5005,
        "hud_listener_port": 5006,
        "websocket_port": 8765
      },
      "vision": {
        "camera_source": 0,  // or URL or File Path
        "model_path": "yolov8n.pt",
        "device": "cpu",     // "cpu", "cuda", "mps"
        "focal_length": 800
      },
      "thresholds": {
        "danger_dist": 3.5,
        "warning_dist": 8.0,
        "tilt_alert": 18.0
      },
      "system": {
        "hud_timeout": 5.0
      }
    }
    ```

### 2. Config Loader (`utils/config_loader.py`)
-   Singleton or Helper function to load `config.json`.
-   Provide default values if file is missing.

### 3. Refactoring
-   Update `main_controller.py`, `vision/fusion.py`, `communication/*.py` to use the loaded config.

## User Experience
-   Users can modify `config.json` to tune system sensitivity without touching code.
