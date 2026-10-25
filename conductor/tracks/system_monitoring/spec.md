# Specification: System Monitoring & Notifications

## Goal
Visualize the connection status of the Core system (Pi 5) and the HUD unit (Pi Zero) within the App, and provide a user notification system for alerts.

## Components

### 1. Backend (`main_controller.py`)
-   **Payload Update**: Add a `system` field to the JSON broadcast.
    ```json
    {
      "timestamp": 123456789,
      "speed": 50,
      "system": {
        "pi5_status": "online",   // Always online if sending
        "hud_status": "online",   // Inferred/Simulated for now
        "cpu_usage": 15.5,        // Optional: Core CPU usage
        "memory_usage": 40.2      // Optional: Core RAM usage
      }
    }
    ```

### 2. Frontend (`app.html`)
-   **Header Update**:
    -   Display **CORE (Pi 5)** status icon.
    -   Display **HUD (Pi Zero)** status icon.
-   **Notification System**:
    -   Overlay component to show toast messages.
    -   Trigger logic:
        -   System Alerts (Disconnects).
        -   Traffic Warnings (High Priority).
        -   Custom "Test Notification" button.

## User Experience
-   **Connected**: Green dots/icons.
-   **Disconnected**: Red dots/icons with pulse animation.
-   **Notification**: Slide-in banner from the top or bottom.
