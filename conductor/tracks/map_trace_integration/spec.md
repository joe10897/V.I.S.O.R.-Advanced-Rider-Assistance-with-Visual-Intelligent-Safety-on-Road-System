# Specification: Map Trace Integration

## Goal
Replace the static map with a dynamic Leaflet.js map that tracks the rider's path (GPS trace) in real-time.

## Components

### 1. Frontend (`app.html`)
-   **Library**: Leaflet.js (via CDN).
-   **Map Component**:
    -   Render OpenStreetMap tiles (Dark Mode preferred).
    -   Marker for current position.
    -   `Polyline` for historical path (trace).
-   **Logic**:
    -   Listen to GPS updates (via `navigator.geolocation` or WebSocket simulation).
    -   Append new coordinates to the path array.
    -   Auto-center map on rider.

## User Experience
-   **Visual**: Dark themed map to match V.I.S.O.R. UI.
-   **Interaction**: User can pan/zoom, but "Auto-follow" re-centers automatically.
