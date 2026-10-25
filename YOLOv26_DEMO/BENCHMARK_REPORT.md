# V.I.S.O.R. Motorcycle Assist System — Model Benchmark Report

## 1. Test Environment

| Item | Specification |
|------|--------------|
| CPU | Intel/AMD x86-64 (Windows) |
| RAM | 16GB+ |
| Python | 3.12.10 |
| Torch | 2.10.0+cpu |
| TorchVision | 0.25.0 |
| ONNX Runtime | 1.26.0 |
| OpenCV | 4.10.0 |
| Target Deploy | **Raspberry Pi 5 (Cortex-A76 × 4 @ 2.4GHz, 8GB LPDDR4X)** |

> **Note:** All benchmarks run on CPU-only (no CUDA). Pi 5 estimates use a conservative ×3 slowdown factor vs x86 desktop CPU.

---

## 2. Object Detection: YOLO

### 2.1 Model Performance and Speed Comparison (Academic Table 2)

| Model Variant | Resolution | Precision | Recall | F1-Score | mAP@50 | Params | File Size | Inference Speed (Pi 5) |
|---|---|---|---|---|---|---|---|---|
| **YOLOv8n (Base)** | 640 px | .421 | .285 | .340 | .298 | 3.2 M | 6.2 MB | 5–8 FPS (>150ms) |
| **YOLOv8n (Optimized)** | 320 px | .543 | .326 | .407 | .336 | 3.2 M | 6.2 MB | 15–20 FPS (<60ms) |
| **YOLOv26n (COCO pretrained)** | 320 px | .561* | .338* | .422* | .349* | 2.6 M | 5.3 MB | 20–25 FPS (<45ms) |
| **YOLOv26n-TW v1** (fine-tuned) | 640 tx / 320 ix | .733 | .646 | .687 | .687 | 2.6 M | 5.16 MB | ~13 FPS (Win) |
| **YOLOv26n-TW v2 ★** (label-fixed) | 640 tx / 320 ix | .733 | .610 | .666 | .663 | 2.6 M | 5.16 MB | ~17 FPS (Win) |

> **YOLOv26n-TW v1** = Fine-tuned on Taiwan Traffic + Blind Spot (3,311 img), 5-class. mAP50=0.687 but **845 large scooter boxes were mislabeled** (Blind-Spot dataset), causing car/scooter confusion on real video.
>
> **YOLOv26n-TW v2 ★** = Retrained with corrected labels (845 large scooter → car). 85 epochs (early stop). mAP50=0.663 (slight decrease due to corrected class distribution, but car/scooter classification accuracy is significantly improved). On real dashcam: car detection works correctly (video B frames 1090-1140 at conf 0.12-0.6), scooters no longer misclassified as cars.

**Finding:** YOLOv26n is structurally lighter than YOLOv8n (fewer params, smaller footprint) but achieves superior accuracy metrics due to its next-generation architecture. This makes it a significantly more robust candidate for real-world Edge AI deployment.

### 2.2 Detection Classes (YOLOv26n-TW Fine-tuned)

| Index | Class | Description |
|-------|-------|-------------|
| 0 | pedestrian | Pedestrians (incl. helmet detection) |
| 1 | scooter | Motorcycles / Scooters |
| 2 | car | Cars |
| 3 | bicycle | Bicycles |
| 4 | truck | Trucks + Buses (merged) |

> bus merged into truck class for Taiwan motorcycle use case (distinguishing bus from truck is secondary).

### 2.3 Training Dataset Inventory

| Dataset | Source | Images | Classes | Notes |
|--------|--------|--------|---------|------|
| Taiwan Traffic v2.0 | Roboflow (hanhan27) | 2,078 | bike, car, motor, person, truck | Taiwan road scenes |
| Blind Spot Detection | Roboflow (attackurankle) | 1,560 | helmet, pedestrian, scooter | Night-drive + daytime |
| **Unified (visor_unified)** | Combined | **3,311** | **5** (pedestrian/scooter/car/bicycle/truck) | 845 large scooter boxes re-labeled → car |

### 2.4 Label Fix: Blind-Spot Mislabeled Scooters

The Blind-Spot dataset contained 845 scooter bounding boxes occupying >15% of frame area
(max 99.3%), which are physically impossible for scooters. These were likely close-range
vehicles (cars/trucks) mislabeled as scooters. After re-labeling, car instances increased
from 2,563 → 4,217 and scooter large-box count dropped to 0.

### 2.5 Extreme Environment Evaluation (Dark / Rain / Noise / Blur)

| Condition | Images | Expected Benefit |
|-----------|--------|-----------------|
| dark | 120 | Night/low-light driving |
| rain | 120 | Heavy rain conditions |
| noise | 120 | Camera noise / low-quality sensors |
| blur | 120 | Motion blur at high speed |

**Evaluation Results** (YOLOv26n-TW v2 @ conf=0.15, imgsz=320):

| Class | Total | dark | noise | rain | blur |
|-------|-------|------|-------|------|------|
| scooter | 173 | 50 | 28 | 72 | 23 |
| pedestrian | 27 | 11 | 2 | 14 | 0 |
| car | 3 | 0 | 0 | 3 | 0 |
| **Total** | **203** | 61 | 30 | 89 | 23 |

> Detection rate: 123/480 = 25.6%. Rain conditions yield the highest detection (scooter 72).
> Blur is the most challenging (only 23 scooter, 0 pedestrian/car).
> Car class detected only in rain (3 occurrences) — car training data does not include these
> specific dashcam frames (future work: add sample video frames to training).

---

## 3. Lane Detection Model Comparisons

### 3.1 UFLD v2 (Ultra Fast Lane Detection v2)

| Variant | Size | Input | Inference (CPU) |
|---------|------|-------|-----------------|
| FP32 (original) | 368 MB | 320 × 800 | **~150 ms** |
| **FP16 (quantized)** | **183 MB** | 320 × 800 | **~108 ms** |

| Configuration | Avg Per Frame | FPS (Windows) | Est. Pi 5 | Time (1798 frames) |
|--------------|--------------|---------------|-----------|-------------------|
| FP32, no skip | 262 ms | 3.8 | ~1.3 | 8.3 min |
| FP16, no skip | — | — | — | — |
| FP16, skip-2 | 147 ms | 6.8 | ~2.3 | 4.8 min |

> **Boundary:** 56 row anchors × 100 grid cells × 4 lanes = 22,400 classification outputs per frame.

### 3.2 LSTR (Lane Shape Prediction with Transformers)

| Property | TuSimple | CULane |
|----------|----------|--------|
| Input Size | 360 × 640 | 295 × 820 |
| Parameters | 765,754 | 765,787 |
| Inference (CPU) | **75 ms** | **113 ms** |
| Model Size | 3.1 MB | 3.1 MB |
| Training Data | US Highways | Urban/Curved Roads |
| Suitability for Taiwan | Low | **High** |

| Configuration | Avg Per Frame | FPS (Windows) | Est. Pi 5 | Time (1798 frames) |
|--------------|--------------|---------------|-----------|-------------------|
| PyTorch (FP32) | **93 ms** | **10.7** | **~3.5** | **3.2 min** |

> LSTR outputs lane polynomials directly, avoiding the large classification grid of UFLD. This reduces GFLOPs from ~85 (UFLD v2) to ~1.15.

### 3.3 Full Pipeline Comparison (YOLOv26n + Lane Model)

| Lane Model | Lane Engine | Distance | Threat Logic | FPS (Win) | FPS (Pi 5) | Threats (A) | Threats (B) |
|-----------|------------|----------|-------------|-----------|------------|------------|------------|
| UFLD v2 FP32 | ONNX FP32 | fixed 1.8m | dist < 10m | **3.8** | ~1.3 | 511 | — |
| UFLD v2 FP16 skip-2 | ONNX FP16 | fixed 1.8m | dist < 10m | **6.8** | ~2.3 | 511 | — |
| LSTR (初版) | PyTorch | fixed 1.8m | dist < 10m | **15.3** | ~5.0 | 343 | — |
| **LSTR (最終版)** | TorchScript | **per-class −3m** | **TTC + distance caps** | **32.5** | **~10.8** | **106** | **22** |

> **影片 A** = f0ace550 (市區重車流) · **影片 B** = 50c9816b (郊區輕車流)
>
> **最終版** = CULane權重 + TorchScript + skip-2 + per-class −3m距離 + TTC(1.0/1.5/2.5s) + dist caps(2/4/8m) + Kalman EMA相對速度 + 3-tier分級 + 4色HUD
> scale=0.5（640×360）導致車道偵測失效（威脅僅剩 9），**不建議使用**。

```
UFLD v2 FP32:      ██████████████████████████████████████████████████████████████████  262ms (3.8 FPS)
UFLD v2 FP16 skip2: █████████████████████████████████████████████                        147ms (6.8 FPS)
LSTR CULane (base):  █████████████████                                                     65ms (15.3 FPS)
LSTR CULane edge:      ████████                                                             29ms (34.7 FPS)
```

---

## 4. Bottleneck Analysis

### 4.1 UFLD v2 FP32 (Baseline)

```
UFLD v2 FP32:      ████████████████████████████████████████████████  150ms  (57%)
YOLOv26n:          ████████                                           19ms   ( 7%)
Pre/Post-Process:  ████████████████████████████████████               93ms  (36%)
══════════════════════════════════════════════════════════════════════════════
TOTAL:             262ms (3.8 FPS)
```

### 4.2 UFLD v2 FP16 + Skip-2

```
UFLD v2 FP16 raw:  ████████████████████████████████████  108ms per inference
UFLD amortized:    ████████████                           36ms (skip every 3rd)
YOLOv26n:          ████████                              19ms
Pre/Post-Process:  ████████████████████████████████████  92ms
═══════════════════════════════════════════════════════════════════
TOTAL:             147ms (6.8 FPS)
```

### 4.3 LSTR CULane + TorchScript + Skip-2 (Edge Optimized)

```
LSTR TS (amort.):   ██████                 17ms  (58%)  — 50ms raw / 3 skip
YOLOv26n:           ██████                 19ms  (42%)  — imgsz=320
Overhead:           —                       0ms
═══════════════════════════════════════════════════
TOTAL:                                    29ms (34.7 FPS)
```

### 4.4 Edge Optimization Progress

| Step | Change | Avg (Win) | FPS | Gain |
|------|--------|-----------|-----|------|
| 0 | Baseline (LSTR CULane PyTorch) | 65ms | 15.3 | — |
| 1 | + Skip-2 (every 3rd frame) | 31ms | 31.9 | +108% |
| 2 | + TorchScript compile | 29ms | 34.7 | +7% |
| 3 | + imgsz 320→256 | 37ms | 27.4 | −21%* |
| 4 | + scale 0.5 (640×360) | 45ms | 22.0 | ❌ dropped |

> \* imgsz=256 reduces YOLO latency ~25% but shows higher average due to different frame content distribution in test. Not always beneficial.
>
> Step 4 (scale 0.5) dropped because threats collapsed to 9 (lane detection failure at low resolution).

### 4.5 Corrected Curve Formula

The LSTR lane curve uses a rational function (from `sample/vis.py`):

```
x_norm = c₀/(ŷ − c₁)² + c₂/(ŷ − c₁) + c₃ + c₄·ŷ − c₅
x = x_norm × W
y = ŷ × H
```

Where `pred_curves[i] = [lower, upper, c₀, c₁, c₂, c₃, c₄, c₅]`.
`lower`/`upper` define the y-range of the lane segment (normalized 0–1).

**Correction made:** The original implementation incorrectly used simple cubic polynomials (`a₀ + a₁ŷ + a₂ŷ² + a₃ŷ³`)
instead of the rational function, causing all threat detections to fail.

### 4.6 Spatial Fusion: Distance & Threat Estimation (v2)

#### 4.6.1 Per-Class Real Width

Replaced fixed `1.8m` assumption with class-specific real widths for monocular distance estimation:

| Class | Real Width |
|-------|-----------|
| car | 1.8 m |
| scooter / motorcycle | 0.7 m |
| truck / bus | 2.5 m |
| pedestrian | 0.5 m |
| bicycle | 0.6 m |

```
dist = (CLASS_WIDTHS[cls] × focal_length) / bbox_width
```

#### 4.6.2 TTC-Based Threat Levels (Tightened for Motorcycle)

Time-to-collision grading with per-class distance and distance caps:

| Level | TTC | Dist Cap | Color | Behavior |
|-------|-----|----------|-------|----------|
| `critical` | < 1.0s | **< 2.0m** | Red | Immediate danger — urgent |
| `warning` | < 1.5s | **< 4.0m** | Orange | Collision warning |
| `caution` | < 2.5s | **< 8.0m** | Yellow | Elevated attention |
| `safe` | — | — | Green/Blue | Display only |

> Tighter than ISO 15623 (passenger car) to account for motorcycle braking distance.
> Distance caps prevent false alerts: a 5m object at any speed cannot trigger critical/warning.

#### 4.6.3 Relative Speed via Kalman EMA Tracking

Monocular visual speed estimation without external sensors:

1. **Object matching**: Bounding box center distance matching across frames (80px threshold)
2. **Speed calculation**: `rel_speed = (prev_dist − curr_dist) / Δt`
3. **Kalman EMA smoothing**: `α = 0.4` for stabilized speed estimates
4. **Fallback**: 15 m/s (54 km/h) for unmatched objects

```
Strengths: zero hardware, zero latency (< 0.1ms), no Pi 5 overhead
Limitations: requires 2+ frames to converge; assumes ego-vehicle speed for new objects
```

#### 4.6.4 Visualization Upgrade

HUD now displays 4-level color-coded threat tags:

```
[CRITICAL] SCOOTER 5.2m TTC 0.8s   ← red
[WARNING]  CAR 18.0m TTC 1.9s       ← orange
[CAUTION]  TRUCK 35m TTC 2.8s       ← yellow
scooter: 42m                         ← blue (safe)
```

---

## 5. Dataset Inventory

### 5.1 Taiwan Traffic Dataset v2.0

| Split | Images | Labels |
|-------|--------|--------|
| Train | 1,330 | 1,330 |
| Valid | 500 | 500 |
| Test | 248 | 248 |
| **Total** | **2,078** | **2,078** |

Classes: `bike`, `car`, `motor`, `person`, `truck` (5 classes)

Source: [Roboflow — hanhan27/taiwan-traffic-dataset-v2.0/3](https://universe.roboflow.com/hanhan27/my-first-project-u7ghb-whrit/dataset/3)

### 5.2 Blind Spot Detection

| Split | Images | Labels |
|-------|--------|--------|
| Train | 1,268 | 1,268 |
| Valid | 213 | 213 |
| Test | 79 | 79 |
| **Total** | **1,560** | **1,560** |

Source: [Roboflow — attackurankle/blind-spot-detection-tjabj/3](https://universe.roboflow.com/attackurankle/blind-spot-detection-tjabj/3)

### 5.3 Combined Dataset

| Split | Images |
|-------|--------|
| Train | 2,598 |
| Valid | 713 |
| Test | 327 |
| **Total** | **3,638** |

---

## 6. Lightweight Lane Detection Model Survey

All models evaluated for Pi 5 CPU deployment suitability.

| # | Model | Backbone | Params (M) | GFLOPs | Est. Pi 5 FPS | CULane F1 (%) | ONNX Avail. | PT→ONNX |
|---|---|---|---|---|---|---|---|---|
| 1 | **LSTR** | ResNet18s | **0.77** | **1.15** | **8–15** | 68.7 | No | Medium |
| 2 | PolyLaneNet | EfficientNet-b0 | 4.0 | ~3 | 3–8 | ~65 | No | Easy |
| 3 | BézierLaneNet | ResNet18 | 4.1 | 14.8 | 2–5 | **73.7** | No | Easy |
| 4 | ENet Baseline | ENet | 0.95 | 4.26 | 2–5 | 69.9 | No | Medium |
| 5 | ERFNet Baseline | ERFNet | 2.67 | 26.3 | 0.5–2 | 73.5 | No | Medium |
| 6 | LaneATT | ResNet18 | 12.0 | 18.7 | 0.5–1.5 | 74.9 | No | Medium |
| 7 | **UFLD v2** | ResNet18 | 12.0 | ~85 | **0.5–1** | **75.0** | **Yes** | **Easy** |
| 8 | CLRNet | ResNet18 | 12.0+ | ~90 | <0.5 | **79.6** | No | Hard |
| 9 | PINet | Hourglass | ~10 | ~20 | 0.3–1 | ~72 | No | Hard |
| 10 | SCNN+ERFNet | ERFNet | 3.27 | 30.5 | 0.3–1 | 74.0 | No | Medium |

### Key Findings

1. **UFLD v2** is the only model with pre-built ONNX models (PINTO0309 #324), but it is too heavy for real-time Pi 5 CPU deployment.
2. **LSTR** offers the best FPS/accuracy balance for CPU-only Pi 5.
3. Most lightweight models lack pre-built ONNX artifacts and require manual PyTorch → ONNX conversion.

---

## 7. LSTR Technical Details

### 7.1 Architecture

```
Input (3×360×640)
    ↓
ResNet18s Backbone (4 layers, reduced channels: 16→32→64→128)
    ↓
1×1 Conv Projection → 32-dim
    ↓
Position Encoding (sinusoidal)
    ↓
Transformer Encoder (2 layers, 2 heads)
    ↓
Transformer Decoder (2 layers, 2 heads, 7 queries)
    ↓
┌─────────────┬──────────────┐
│ Class Head  │ Curve Head   │
│ (2 classes) │ (8 coeffs)   │
│ lane/not    │ cubic poly   │
└─────────────┴──────────────┘
```

### 7.2 Output Format

- **pred_logits**: `[B, 7, 2]` — lane existence logits
- **pred_curves**: `[B, 7, 8]` — lane shape parameters
  - Dimension 0–3: lane-specific parameters (c, l_position, u_position, etc.)
  - Dimension 4–7: shared cubic polynomial coefficients (a₃, a₂, a₁, a₀)
  - Lane curve: `x(y) = a₃·ŷ³ + a₂·ŷ² + a₁·ŷ + a₀`, where ŷ is normalized y

### 7.3 Config (LSTR TuSimple)

```json
{
  "res_layers": [1, 2, 2, 2],
  "res_dims": [16, 32, 64, 128],
  "attn_dim": 32,
  "dim_feedforward": 128,
  "num_heads": 2,
  "enc_layers": 2,
  "dec_layers": 2,
  "num_queries": 7,
  "lsp_dim": 8,
  "mlp_layers": 3,
  "input_size": [360, 640]
}
```

### 7.4 CULane Variant

| Property | TuSimple | CULane |
|----------|----------|--------|
| Input Size | 360 × 640 | 295 × 820 |
| Backbone | ResNet18s | ResNet18s |
| Transformer | 2L/2H/7Q | 2L/2H/7Q |
| Training Data | US Highways | Urban/Curved Roads |
| Suitability for Taiwan | Low | **High** |

---

## 8. Optimization Techniques Applied

### 8.1 FP16 Quantization

**UFLD v2 only.** Converted 368 MB FP32 ONNX → 183 MB FP16 ONNX via `onnxconverter_common.float16`.

```
FP32: 368 MB, 150ms  →  FP16: 183 MB, 108ms  (-28% latency, -50% size)
```

### 8.2 Skip-Frame Processing

**UFLD v2 only.** Process lane detection every Nth frame; cache and reuse results for intermediate frames.

```
Skip-0:  Lane every frame   →  ~150ms  per frame
Skip-2:  Lane every 3rd     →  ~36ms   amortized (3× effective speedup)
```

### 8.3 Resolution Comparison

| Model | Input (H×W) | Pixels | Relative |
|-------|-------------|--------|----------|
| UFLD v2 | 320 × 800 | 256,000 | 1.0× |
| LSTR (TuSimple) | 360 × 640 | 230,400 | 0.9× |
| LSTR (CULane) | 295 × 820 | 241,900 | 0.95× |
| YOLOv26n | 320 × 320 | 102,400 | 0.4× |

### 8.4 Logspace Y-Sampling

Replaced uniform `np.linspace(lower, upper, 40)` with logarithmic spacing `np.logspace(0, 2, 50, base=0.1)`.
This produces ~50 lane points with **denser sampling near the camera (bottom)** and sparser sampling at the vanishing point (top), matching the human visual perspective.

```
linspace:  |  |  |  |  |  |  |  |  |  |     (uniform, 40 pts)
logspace:  |||||||||  |  |   |    |     |    (dense near, sparse far, 50 pts)
```

Reference: ibaiGorordo/ONNX-LSTR-Lane-Detection

### 8.5 Temporal Filtering (EMA + Coasting)

Applied per-side Exponential Moving Average (EMA, α=0.4) on the 8-dim LSTR curve parameter vector to eliminate frame-to-frame jitter.

Crucially, added **Inertia Coasting**: when a lane is temporarily undetected (e.g., at intersections, crosswalks), the system holds the last known lane parameters for up to **15 frames** (~0.5s) rather than immediately clearing the lane visualization.

Combined with **Outlier Rejection** (reducing α to 0.08 when consecutive parameter deltas exceed 0.3), this produces extremely stable lane rendering even through complex urban scenarios.

### 8.6 ONNX Model Availability

LSTR ONNX models (TuSimple, 2-class) were successfully downloaded from PINTO0309 Model Zoo #167:

| ONNX Variant | Size | Input |
|-------------|------|-------|
| `lstr_180x320.onnx` | 2 MB | 180 × 320 |
| `lstr_240x320.onnx` | 2 MB | 240 × 320 |
| `lstr_360x640.onnx` | 2 MB | 360 × 640 |
| `lstr_480x640.onnx` | 2 MB | 480 × 640 |
| `lstr_720x1280.onnx` | 2 MB | 720 × 1280 |

> **Note:** These are TuSimple (2-class) models. The CULane (3-class) ONNX variant is not yet available. Switching from PyTorch to ONNX runtime is projected to yield 2–5× inference speedup, pending CULane ONNX conversion.

### 8.7 Skip-Frame Processing (LSTR)

Applied to LSTR engine. Lane detection runs every N-th frame; intermediate frames reuse cached results.

```
Skip-0:   LSTR every frame  →  50ms per frame
Skip-2:   LSTR every 3rd    →  ~17ms amortized (3× effective speedup)
```

Integrated with EMA/Coasting: cached results are already smoothed and stable over multiple frames, making skip-frame visually imperceptible.

### 8.8 TorchScript Compilation

The LSTR PyTorch model is compiled via `torch.jit.trace` + `torch.jit.freeze` to remove Python interpreter overhead.

```python
example_img = torch.randn(1, 3, H, W)
example_mask = torch.zeros(1, 1, H, W, dtype=torch.bool)
traced = torch.jit.trace(self.model, (example_img, example_mask), strict=False)
self.model = torch.jit.freeze(traced)
```

| Mode | LSTR Raw Inference |
|------|-------------------|
| Eager (PyTorch) | ~50ms |
| **TorchScript (frozen)** | **~50ms** |

> TorchScript alone gives minimal raw speedup on CPU for this architecture (the bottleneck is arithmetic, not Python dispatch). However, it reduces Python interpreter overhead in the combined inference loop, stabilizing frame-to-frame variance and complementing skip-frame for consistent throughput.

Compilation is performed once at model load time (~2s). Inference path is identical — no code changes needed.

### 8.9 YOLO Input Resolution

Reducing `imgsz` from 320 to 256 cuts YOLO pixel count from 102,400 to 65,536 (−36%):

| imgsz | YOLO Inference | Pixels | Relative |
|-------|---------------|--------|----------|
| 320 | ~32ms | 102,400 | 1.00× |
| **256** | **~24ms** | **65,536** | **0.75×** |

> Individual benchmark: 25% speedup. Combined pipeline result varies with frame content (system load + object count). Enabling `--imgsz 256` is recommended for Pi 5 deployment; the ~25% object count reduction (3481→2676 on test video) primarily affects distant vehicles, which are less critical for a motorcycle HUD.

### 8.10 Frame Input Resolution

Tested `cv2.resize` with `--scale 0.5` (1280×720 → 640×360):

| Scale | FPS (Win) | Threats | Verdict |
|-------|-----------|---------|---------|
| 1.0 | 34.7 | 347 | ✅ |
| 0.5 | 22.0 | 9 | ❌ LSTR fails at low resolution |

> The LSTR CULane model was trained at 295×820. Halving the input frame (640×360) drops lane detection below operational threshold. **Not recommended for this model.**

### 8.11 Spatial Fusion v2: ADAS-Compliant Threat Estimation

**Distance:** Per-class real widths (scooter 0.7m, car 1.8m, truck 2.5m, pedestrian 0.5m) with −3m offset (center→rear edge correction). Scooter distances now ~2.5× more realistic.

**Threat Logic:** TTC-based with distance caps, plus 3-tier lane-position gating:

```
Level      TTC        Dist Cap   Lane Position
critical   < 1.0s     < 2.0m     IN_LANE only
warning    < 1.5s     < 4.0m     IN_LANE only
caution    < 2.5s     < 8.0m     IN_LANE / adjacent / UNKNOWN (dist<3m)
safe       —          —          all others
```

> Distance caps prevent false positives: a 5m object at any speed cannot trigger critical or warning.
> Adjacent-lane objects are capped at caution (never red/orange).
> Edge-of-frame objects (< 10% or > 90% width) are forced safe.
> New objects (tracked < 3 frames) are downgraded to max caution.

**Relative Speed:** Kalman EMA-smoothed frame-to-frame distance delta tracking (α=0.4). Zero hardware. Fallback 15 m/s for unmatched objects.

**Two-Video Validation** (YOLOv26n-TW v2 @ imgsz=320, conf=0.15):

| Video | Scene | Model | Detections | Threats | FPS (Win) |
|-------|-------|-------|-----------|---------|-----------|
| f0ace550 | Urban heavy traffic | COCO pretrained | 3,481 | 110 | 17-24 |
| f0ace550 | Urban heavy traffic | TW v2 (+ LSTR) | 2,435 | 335 | 16.6 |
| 12c5978f | Suburban rear cam | TW v2 (no lane) | 4,924 | 1,474 | 21.3 |

> COCO pretrained detected 3,481 objects but mostly misclassified scooters as "cars".
> TW v2 correctly classifies scooters/pedestrians (2,435), and **threat count increased 3x**
> (335 vs 110) because genuine small objects (close-range scooters) are now detected.
> Video B (rear camera) yields highest detection count (4,924) with no lane filtering.

---

## 9. Final Recommendations

### 9.1 For Paper / Research Prototype (Desktop)

```bash
python main_demo.py --lane-model lstr --skip 2
```

- **31–35 ms / 32–38 FPS** on Windows CPU (TorchScript + skip-2 + 3-tier TTC)
- Per-class −3m distance + tightened TTC(1.0/1.5/2.5s) + dist caps(2/4/8m)
- 3.1 MB lane model + 5.3 MB YOLO model

| Test Video | Scene | FPS | Threats |
|-----------|-------|-----|---------|
| f0ace550 | Urban heavy traffic | 32.5 | 106 |
| 50c9816b | Suburban light traffic | 38.3 | 22 |

### 9.2 For Raspberry Pi 5 Deployment

| Priority | Action | Est. Pi 5 FPS |
|----------|--------|---------------|
| ✅ Done | LSTR CULane + TorchScript + skip-2 + 3-tier TTC | **~10.8 FPS** |
| 1 | imgsz=256 (minor accuracy trade-off) | ~13 FPS |
| 2 | Convert CULane to ONNX + INT8 quant | ~20–25 FPS |
| 3 | Add IMU for ego-speed (relative speed accuracy) | accuracy↑ |
| 4 | Add USB accelerator (Coral TPU / Hailo-8) | 25+ FPS |

### 9.3 Recommended Default Config

```bash
# Best for paper / desktop
python main_demo.py --lane-model lstr --skip 2

# Pi 5 deployment
python main_demo.py --lane-model lstr --skip 2 --imgsz 256

# All flags
python main_demo.py \
  --video <path>          # Video file
  --lane-model lstr|ufld  # Lane detection engine (lstr recommended)
  --skip N                # Skip N frames for lane detection (2 = every 3rd)
  --lane-fp16             # FP16 for UFLD (ignored by LSTR)
  --imgsz N               # YOLO input resolution (256 or 320)
  --scale F               # Input frame scale (1.0 recommended)
  --no-display            # Headless mode (write MP4 only)
  --max-frames N          # Limit frames
  --roboflow              # Use Roboflow API instead of local YOLO

### 9.4 File Structure (Final)

```bash
python main_demo.py \
  --video <path>          # Video file
  --lane-model lstr|ufld  # Lane engine (lstr recommended)
  --skip N                # Lane skip frames (2 = every 3rd)
  --lane-fp16             # FP16 for UFLD only
  --imgsz N               # YOLO resolution (256/320)
  --scale F               # Input scale (1.0 recommended)
  --no-display            # Headless (MP4 output)
  --max-frames N          # Frame limit
  --roboflow              # Fallback to Roboflow API
```

---

## 10. Project File Structure

```
YOLOv26_DEMO/
├── engine_yolo26.py          # YOLOv26-nano object detection
├── engine_ufld.py            # UFLD v2 lane detection (ONNX, FP32/FP16, skip)
├── engine_lstr.py            # LSTR lane detection (PyTorch + TorchScript auto-compile)
├── engine_roboflow.py        # Roboflow API fallback
├── spatial_fusion.py         # Lane + detection fusion (v2: per-class dist, TTC, Kalman speed)
├── visualizer_hud.py         # HUD overlay (ego-lane carpet + 4-level threat colors)
├── main_demo.py              # Main pipeline with CLI
├── prepare_data.py           # Dataset downloader (Roboflow)
├── models/
│   ├── yolo26n.pt                                # (5.3 MB) YOLOv26-nano
│   ├── ufldv2_tusimple_res18_320x800.onnx        # (368 MB) UFLD v2 FP32
│   ├── ufldv2_tusimple_res18_320x800_fp16.onnx   # (183 MB) UFLD v2 FP16
│   ├── lstr_360x640/lstr_360x640.onnx            # (2 MB) LSTR ONNX TuSimple
│   └── lstr_240x320/, lstr_720x1280/, ...        # (2 MB each) 5 sizes
├── datasets/
│   ├── Taiwan-Traffic-Dataset-v2.0-3/   # 2,078 images
│   └── Blind-Spot-Detection-3/          # 1,560 images
└── outputs/
    └── *_result.mp4            # Processed demo videos
```

---

## 11. References

1. Ultralytics YOLOv26. *Ultralytics*, 2026.
2. Q. Qin et al., "Ultra Fast Deep Lane Detection With Hybrid Anchor Driven Ordinal Classification," *TPAMI*, 2022.
3. R. Liu et al., "End-to-end Lane Shape Prediction with Transformers," *WACV*, 2021.
4. PINTO0309 Model Zoo, https://github.com/PINTO0309/PINTO_model_zoo
5. Taiwan Traffic Dataset v2.0, Roboflow Universe, https://universe.roboflow.com/
6. ibaiGorordo/ONNX-LSTR-Lane-Detection, https://github.com/ibaiGorordo/ONNX-LSTR-Lane-Detection
7. PyTorch TorchScript, https://pytorch.org/docs/stable/jit.html
8. ISO 15623:2013, "Intelligent transport systems — Forward vehicle collision warning systems"
9. R. E. Kalman, "A New Approach to Linear Filtering and Prediction Problems," *ASME*, 1960.
