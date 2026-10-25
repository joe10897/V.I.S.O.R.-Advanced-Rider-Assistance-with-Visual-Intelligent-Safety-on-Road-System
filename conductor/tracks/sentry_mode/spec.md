# Specification: Sentry Mode

## Goal
Implement a security monitoring system that records video when suspicious activity (vibration or visual motion) is detected while the system is armed.

## Components

### 1. Backend (`vision/recorder.py`)
-   **Circular Buffer**: Continuously cache the last N seconds (e.g., 5s) of video frames in memory.
-   **Event Recorder**: When triggered, write the buffer + next M seconds (e.g., 10s) to disk.
-   **File Management**: Save files as `events/sentry_YYYYMMDD_HHMMSS.mp4`.

### 2. Trigger Logic (`main_controller.py`)
-   **Arming**: Receive `sentry_mode: true/false` via WebSocket.
-   **Triggers**:
    -   **IMU**: High G-force or Tilt change (Simulated for now).
    -   **Vision**: Significant pixel changes (Motion Detection) or specific object detection (Person/Car) in ROI.

### 3. Notification
-   Send `event_notification` to App via WebSocket when recording is saved.

## Data Flow
1. App sends `{"action": "set_sentry", "enabled": true}`.
2. Controller enters Sentry State.
3. `SensorSim` generates a "shock" (simulated).
4. Controller triggers `Recorder.save_event()`.
5. Video saved to `events/`.
6. Controller sends `{"type": "event", "msg": "Sentry Event Detected"}` to App.
