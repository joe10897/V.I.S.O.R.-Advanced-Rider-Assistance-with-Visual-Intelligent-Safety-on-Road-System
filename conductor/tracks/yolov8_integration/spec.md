# Specification: YOLOv8 Integration

## Goal
Integrate YOLOv8 object detection into the `main_controller.py` to provide real-time environmental awareness and hazard warnings to the rider via the HUD/App.

## Core Components

### 1. Model Inference (`model_inference.py`)
-   **Model**: YOLOv8 Nano (`yolov8n.pt`) for performance on Edge devices.
-   **Input**: Video frames (numpy array).
-   **Output**: Detections containing class ID, confidence score, and bounding box coordinates.
-   **Classes of Interest**:
    -   Car (COCO ID: 2)
    -   Motorcycle (COCO ID: 3)
    -   Bus (COCO ID: 5)
    -   Truck (COCO ID: 7)

### 2. Main Controller (`main_controller.py`)
-   **Frame Capture**:
    -   Must capture frames from a video source (Camera or File).
    -   Should run in a non-blocking manner (separate thread/process) to not stall the async event loop.
-   **Inference Loop**:
    -   Process frames at a target rate (e.g., 10-15 FPS on Pi 5).
    -   Integrate `Fusion` logic to determine threat levels.
-   **Data Broadcast**:
    -   Update the `broadcast_data` payload with real-time detection info.
    -   Payload format must be compatible with Frontend (App).

### 3. Data Schema (WebSocket/UDP)
The JSON payload sent to clients should follow this structure:

```json
{
  "timestamp": 1700000000.0,
  "speed": 65.5,             // km/h (from GPS/OBD or simulation)
  "tilt": 12.3,              // degrees (from IMU or simulation)
  "warning": {               // Optional, null if no warning
    "direction": "rear",     // "front", "rear", "left", "right"
    "level": "danger",       // "info", "warning", "danger"
    "message": "Vehicle approaching"
  },
  "debug": {                 // Optional debug info
    "fps": 12.5,
    "objects_count": 2
  }
}
```

## Success Criteria
1.  `main_controller.py` runs without crashing.
2.  Video frames are processed by YOLOv8.
3.  Detections are correctly classified as threats (using existing `Fusion` logic).
4.  Warning messages are received by `app.html` via WebSocket.
5.  System maintains stable framerate (aiming for >10 FPS).
