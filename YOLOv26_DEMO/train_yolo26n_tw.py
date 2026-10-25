from ultralytics import YOLO
import time
import os
import shutil

if __name__ == "__main__":
    model = YOLO("models/yolo26n.pt")

    results = model.train(
        data="datasets/visor_unified.yaml",
        epochs=100,
        imgsz=640,
        batch=8,
        device=0,
        optimizer="auto",
        lr0=0.01,
        lrf=0.01,
        scale=0.7,
        mosaic=1.0,
        copy_paste=0.15,
        multi_scale=False,
        close_mosaic=15,
        degrees=5,
        translate=0.1,
        fliplr=0.5,
        hsv_h=0.015,
        hsv_s=0.5,
        hsv_v=0.4,
        erasing=0.3,
        patience=20,
        pretrained=True,
        project="runs/visor_train",
        name="yolo26n_tw_v2",
        exist_ok=True,
        seed=0,
    )

    best = str(results.save_dir) + "/weights/best.pt"

    # Deploy to models/
    dst = os.path.join("models", "yolo26n_tw.pt")
    shutil.copy2(best, dst)
    print("=" * 50)
    print("TRAIN DONE")
    print("Best weights:", best)
    print("Deployed ->", dst)
    print("=" * 50)

    # Auto-eval on extreme images
    print("\n[EVAL] Testing on extreme images (dark/noise/rain/blur)...")
    from eval_extreme import eval_extreme
    eval_extreme(best, r"..\img2blur\extreme_images")

