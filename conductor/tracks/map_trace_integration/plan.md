# Implementation Plan: Map Trace Integration

## Phase 1: Frontend Setup
- [x] **Task 1: Add Leaflet Dependencies**
    -   Add Leaflet CSS and JS to `<head>`.
- [x] **Task 2: Implement Map Component**
    -   Create a React component `LeafletMap`.
    -   Implement tile layer (Dark Matter or similar).
    -   Implement Marker and Polyline logic.

## Phase 2: Integration
- [x] **Task 3: Connect to Location Data**
    -   Ensure `location` state updates trigger map updates.
    -   Handle "Simulation Mode" to generate a fake path for testing.

## Phase 3: Verification
- [x] **Task 4: Test Path Drawing**
    -   Enable simulation and verify the blue line follows the rider.
