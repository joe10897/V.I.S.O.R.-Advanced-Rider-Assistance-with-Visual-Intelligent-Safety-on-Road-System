# Implementation Plan: Configuration Management

## Phase 1: Setup
- [x] **Task 1: Create Default Config**
    -   Create `config.json` with current default values.
- [x] **Task 2: Create Loader Module**
    -   Implement `load_config()` in `utils.py` (or new module).

## Phase 2: Refactoring
- [x] **Task 3: Refactor Vision Module**
    -   Update `fusion.py` to accept thresholds via `__init__`.
    -   Update `detector.py` to accept model path/device.
- [x] **Task 4: Refactor Main Controller**
    -   Load config at startup.
    -   Pass config values to `UdpBroadcaster`, `UdpListener`, `VisorWebSocketServer`.

## Phase 3: Verification
- [x] **Task 5: Test Config Loading**
    -   Verify the system starts with `config.json`.
    -   Verify changing a value (e.g., port) reflects in the system.
