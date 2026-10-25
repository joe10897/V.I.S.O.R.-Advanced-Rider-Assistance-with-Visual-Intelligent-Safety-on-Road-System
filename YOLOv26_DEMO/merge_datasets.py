import os
import shutil
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
DATASETS = os.path.join(BASE, "datasets")
OUT = os.path.join(DATASETS, "visor_unified")

# Unified class mapping: unified_id -> name
UNIFIED_NAMES = {
    0: "pedestrian",
    1: "scooter",
    2: "car",
    3: "bicycle",
    4: "truck",   # includes bus
}

# source dataset -> {source_class_id: unified_class_id}  (None = skip)
SRC_MAP = {
    "Blind-Spot-Detection-3": {
        0: 0,   # helmet -> pedestrian
        1: 0,   # pedestrian -> pedestrian
        2: 1,   # scooter -> scooter
    },
    "Taiwan-Traffic-Dataset-v2.0-3": {
        0: 3,   # bike -> bicycle
        1: 2,   # car -> car
        2: 1,   # motor -> scooter
        3: 0,   # person -> pedestrian
        4: 4,   # truck -> truck
    },
}

# source splits -> output split
SPLITS = {"train": "train", "valid": "val"}


def rewrite_labels(src_labels_dir, dst_labels_dir, cls_map):
    stats = defaultdict(int)
    reclassify_large_scooter = defaultdict(int)  # track re-labeling
    for fn in os.listdir(src_labels_dir):
        if not fn.endswith(".txt"):
            continue
        src_path = os.path.join(src_labels_dir, fn)
        out_lines = []
        with open(src_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split()
                cid = int(parts[0])
                if cid not in cls_map:
                    continue  # skip unmapped class
                new_cid = cls_map[cid]

                # Fix: Blind-Spot scooter boxes > 15% frame area → re-label as car
                # (845 mislabeled large boxes in Blind-Spot cause model to
                #  confuse large cars as scooters)
                if len(parts) >= 5:
                    w, h = float(parts[3]), float(parts[4])
                    if w * h > 0.15 and new_cid == 1:  # scooter
                        new_cid = 2  # → car
                        reclassify_large_scooter["car"] += 1

                out_lines.append(f"{new_cid} " + " ".join(parts[1:]))
                stats[new_cid] += 1
        if out_lines:
            with open(os.path.join(dst_labels_dir, fn), "w") as f:
                f.write("\n".join(out_lines) + "\n")
    if reclassify_large_scooter:
        print(f"  [re-labeled large scooter → car: {reclassify_large_scooter['car']} boxes]")
    return stats


def main():
    if os.path.exists(OUT):
        shutil.rmtree(OUT)

    per_split_stats = defaultdict(lambda: defaultdict(int))

    for src_name, cls_map in SRC_MAP.items():
        src_dir = os.path.join(DATASETS, src_name)
        for src_split, dst_split in SPLITS.items():
            src_img = os.path.join(src_dir, src_split, "images")
            src_lab = os.path.join(src_dir, src_split, "labels")
            if not os.path.isdir(src_img):
                continue
            dst_img = os.path.join(OUT, dst_split, "images")
            dst_lab = os.path.join(OUT, dst_split, "labels")
            os.makedirs(dst_img, exist_ok=True)
            os.makedirs(dst_lab, exist_ok=True)

            imgs = [f for f in os.listdir(src_img) if f.lower().endswith((".jpg", ".jpeg", ".png"))]
            for img in imgs:
                base = os.path.splitext(img)[0]
                # YOLO dataset: image <-> label share same basename
                label_file = base + ".txt"
                src_label_path = os.path.join(src_lab, label_file)
                if os.path.exists(src_label_path):
                    shutil.copy2(os.path.join(src_img, img), os.path.join(dst_img, img))

            stats = rewrite_labels(src_lab, dst_lab, cls_map)
            for cid, cnt in stats.items():
                per_split_stats[dst_split][cid] += cnt
            print(f"[{src_name}/{src_split}] -> {dst_split}: {len(imgs)} images, labels rewritten")

    # Write data.yaml
    yaml_content = "names:\n"
    for i in range(len(UNIFIED_NAMES)):
        yaml_content += f"- {UNIFIED_NAMES[i]}\n"
    yaml_content += f"nc: {len(UNIFIED_NAMES)}\n"
    yaml_content += "train: ../visor_unified/train/images\n"
    yaml_content += "val: ../visor_unified/val/images\n"
    with open(os.path.join(DATASETS, "visor_unified.yaml"), "w") as f:
        f.write(yaml_content)

    print("\n=== Unified Dataset Summary ===")
    for split in ["train", "val"]:
        img_dir = os.path.join(OUT, split, "images")
        n_imgs = len(os.listdir(img_dir)) if os.path.isdir(img_dir) else 0
        print(f"{split}: {n_imgs} images")
    print("\n=== Class instance distribution (per split) ===")
    for split, stats in per_split_stats.items():
        print(f"{split}: {dict(stats)}")
    print(f"\nDone. Output: {OUT}")


if __name__ == "__main__":
    main()
