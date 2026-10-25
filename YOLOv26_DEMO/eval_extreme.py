"""V.I.S.O.R. Extreme Environment Evaluation.
Runs trained model on 480 extreme (dark/noise/rain/blur) images,
outputs per-class detection stats to verify model robustness.
"""
import cv2
import os
from collections import Counter
from ultralytics import YOLO


def eval_extreme(model_path, source_dir, output_dir="runs/visor_extreme"):
    """Evaluate a trained YOLO model on extreme-condition images."""
    model = YOLO(model_path)
    os.makedirs(output_dir, exist_ok=True)

    conditions = Counter()
    det_counts = Counter()
    all_dets = Counter()
    total_img = 0
    images_with_dets = 0

    for fn in sorted(os.listdir(source_dir)):
        if not fn.lower().endswith((".png", ".jpg", ".jpeg")):
            continue
        total_img += 1
        cond = fn.split("_")[0]
        conditions[cond] += 1

        img_path = os.path.join(source_dir, fn)
        frame = cv2.imread(img_path)
        if frame is None:
            continue

        results = model.predict(frame, conf=0.15, imgsz=320, verbose=False)
        dets = results[0].boxes

        if len(dets) > 0:
            images_with_dets += 1
            for box in dets:
                cls_name = model.names.get(int(box.cls[0]), "?")
                det_counts[cls_name] += 1
                all_dets[(cond, cls_name)] += 1

    # Print summary
    print("=" * 55)
    print(f" Extreme Eval: {total_img} images (conf=0.15)")
    print("=" * 55)
    print(f"{'Class':14} {'Total':>6}  {'dark':>6} {'noise':>6} {'rain':>6} {'blur':>6}")
    print("-" * 55)
    for cls_name in sorted(det_counts.keys()):
        dark = all_dets.get(("dark", cls_name), 0)
        noise = all_dets.get(("noise", cls_name), 0)
        rain = all_dets.get(("rain", cls_name), 0)
        blur = all_dets.get(("blur", cls_name), 0)
        print(f"{cls_name:14} {det_counts[cls_name]:6d}  {dark:6d} {noise:6d} {rain:6d} {blur:6d}")

    print("-" * 55)
    print(f"{'TOTAL':14} {sum(det_counts.values()):6d}")
    print(f"\nImages with detections: {images_with_dets}/{total_img}")
    print(f"Detection rate: {images_with_dets/total_img*100:.1f}%")
    print("=" * 55)
    return det_counts, images_with_dets


if __name__ == "__main__":
    import sys
    model_path = sys.argv[1] if len(sys.argv) > 1 else "models/yolo26n_tw.pt"
    source_dir = sys.argv[2] if len(sys.argv) > 2 else r"..\img2blur\extreme_images"
    eval_extreme(model_path, source_dir)
