import json
import os
import copy

DEFAULT_CONFIG = {
  "network": {
    "broadcast_ip": "255.255.255.255",
    "udp_port": 5005,
    "hud_listener_port": 5006,
    "websocket_port": 8765,
    "websocket_host": "0.0.0.0"
  },
  "vision": {
    "source": None,
    "model_path": "yolov8n.pt",
    "device": "cpu",
    "focal_length": 800,
    "conf_threshold": 0.25
  },
  "thresholds": {
    "danger_dist": 3.5,
    "warning_dist": 8.0,
    "tilt_alert": 18.0,
    "rear_threat_cy": 0.4
  },
  "system": {
    "hud_timeout": 5.0
  }
}

def load_config(path="config.json"):
    if not os.path.exists(path):
        print(f"[WARN] Config file {path} not found. Using defaults.")
        return copy.deepcopy(DEFAULT_CONFIG)
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            user_config = json.load(f)
            # Merge with defaults (deep merge is better, but keeping it simple for now)
            config = copy.deepcopy(DEFAULT_CONFIG)
            for section, values in user_config.items():
                if section in config and isinstance(values, dict):
                    config[section].update(values)
                else:
                    config[section] = values
            return config
    except Exception as e:
        print(f"[ERROR] Failed to load config: {e}. Using defaults.")
        return copy.deepcopy(DEFAULT_CONFIG)

def save_config(config, path="config.json"):
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        print(f"[INFO] Config saved to {path}")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to save config: {e}")
        return False
