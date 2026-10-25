# Implementation Plan: YOLOv8 Integration

## Phase 1: Foundation & Refactoring
- [x] **Task 1: Prepare `FrameReader` Module**
    -   Extract `FrameReader` class from `main.py` into a reusable module `vision/frame_reader.py`.
    -   Ensure it handles video files and camera streams robustly.
- [x] **Task 2: Optimize `model_inference.py`**
    -   Ensure `Detector` class is initialized efficiently.
    -   Add filtering for specific classes (Car, Bus, Truck, Bike) directly in the detection method or a wrapper.

## Phase 2: Controller Integration
- [x] **Task 3: Integrate Vision System into `MainController`**
    -   Import `FrameReader`, `Detector`, `Fusion`, `CentroidTracker`.
    -   Initialize these components in `MainController.__init__`.
    -   Create a `vision_loop` method (or integrate into `main_loop`) to handle frame capture and processing.
- [x] **Task 4: Implement Threat Logic & Data Payload**
    -   Map `Fusion` output (Threat Levels) to the new JSON Data Schema.
    -   Replace `generate_dummy_data` with real sensor/vision data.

## Phase 3: Testing & Verification
- [x] **Task 5: Integration Test**
    -   Run `main_controller.py` with a sample video file.
    -   Verify logs show detections and warnings.
- [x] **Task 6: Frontend Verification**
    -   Update `app.html` if necessary to parse the new data format.
    -   Launch `app.html` and verify visual alerts appear when playing a "crash/danger" sample video.
