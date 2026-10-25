# Implementation Plan: Sentry Mode

## Phase 1: Recording Infrastructure
- [x] **Task 1: Implement `VideoRecorder` Module**
    - Create `vision/recorder.py`.
    - Implement a `CircularBuffer` to keep recent frames in memory (pre-roll).
    - Implement `save_event(filename)` to flush buffer and record subsequent frames to disk.

## Phase 2: Controller Logic
- [x] **Task 2: Handle Frontend Commands**
    - Update `VisorWebSocketServer` or `MainController` to receive and store the `sentry_mode` state.
- [x] **Task 3: Implement Detection Triggers**
    - Add simple motion detection (frame subtraction) to `vision/detector.py` or a new module.
    - Connect `SensorSim` vibration alerts to the trigger logic.

## Phase 3: Integration & Verification
- [x] **Task 4: Integrate into Main Loop**
    - When `sentry_mode` is active, feed frames into the circular buffer.
    - Monitor triggers and initiate recording.
- [x] **Task 5: Frontend Notification & Testing**
    - Send a WebSocket message when a sentry event occurs.
    - Verify `.mp4` files are correctly generated in the `events/` folder.
