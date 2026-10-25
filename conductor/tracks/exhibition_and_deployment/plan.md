# Implementation Plan: Exhibition & Deployment

## Phase 1: Deployment Automation
- [x] **Task 1: Create `scripts/deploy_pi5.sh`**
    - Install system dependencies (OpenCV, V4L2).
    - Create virtual environment and install requirements.
    - Setup systemd service for `MainController`.
- [x] **Task 2: Create `scripts/deploy_pizero.sh`**
    - Install I2C and font dependencies.
    - Create virtual environment and install requirements.
    - Setup systemd service for `HudClient`.

## Phase 2: Demo Mode Optimization
- [x] **Task 3: Implement Demo Logic in `MainController`**
    - Add `--demo` CLI flag to force video source and sensor sim.
    - Implement automatic looping for demo videos.
    - Ensure system status (CPU/Temp) reflects a "Demo" state if needed.
- [x] **Task 4: Create `scripts/test_all.py`**
    - A quick diagnostic script to verify Wi-Fi, WebSocket, and UDP connectivity in one go.

## Phase 3: Exhibition Verification
- [ ] **Task 5: Deployment Test**
    - Verify scripts on clean OS image (or simulation).
