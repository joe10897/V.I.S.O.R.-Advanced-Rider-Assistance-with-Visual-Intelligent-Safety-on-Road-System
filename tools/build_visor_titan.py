#!/usr/bin/env python3
# ==============================================================================
#  V.I.S.O.R. Titan Dataset Auto-Extractor & Assembler
#  自動抽取與組裝腳本：
#  1. 從 BDD100K (70,000 張) 中精選近距離大車 (面積 > 12%)、高密度交通與純負樣本
#  2. 修復並融合台灣在地化數據 (移除 >15% 機車誤標為汽車的 Bug)
#  3. 生成 4:3 比例標準化對齊之 VISOR-Titan 旗艦級訓練數據集
# ==============================================================================

import os
import sys
import shutil
import random
import argparse
from collections import defaultdict

# Windows utf-8 console safety
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 統一 5 大類別定義
UNIFIED_CLASSES = {
    0: "pedestrian",
    1: "scooter",
    2: "car",
    3: "bicycle",
    4: "truck",  # 包含 bus, truck
}

# BDD100K 原始類別映射至 VISOR 類別
# BDD: 0:person, 1:rider, 2:car, 3:bus, 4:truck, 5:bike, 6:motor
BDD_MAP = {
    0: 0,  # person -> pedestrian
    1: 1,  # rider -> scooter
    2: 2,  # car -> car
    3: 4,  # bus -> truck
    4: 4,  # truck -> truck
    5: 3,  # bike -> bicycle
    6: 1,  # motor -> scooter
}

# 台灣在地化數據集映射
TW_DATASETS = {
    "Taiwan-Traffic-Dataset-v2.0-3": {
        0: 3,  # bike -> bicycle
        1: 2,  # car -> car
        2: 1,  # motor -> scooter
        3: 0,  # person -> pedestrian
        4: 4,  # truck -> truck
    },
    "Blind-Spot-Detection-3": {
        0: 0,  # helmet -> pedestrian
        1: 0,  # pedestrian -> pedestrian
        2: 1,  # scooter -> scooter
    },
    "Blind-Spot-Detection.v7i.yolo26": {
        0: 0,  # helmet -> pedestrian
        1: 0,  # pedestrian -> pedestrian
        2: 1,  # scooter -> scooter
    }
}


def parse_label_file(file_path):
    """解析單個 YOLO 標籤檔案，回傳各標註物體列表"""
    boxes = []
    if not os.path.exists(file_path):
        return boxes
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 5:
                    cid = int(parts[0])
                    cx, cy, w, h = map(float, parts[1:5])
                    boxes.append((cid, cx, cy, w, h))
    except Exception:
        pass
    return boxes


def scan_bdd_dataset(bdd_dir, split="train", max_large=4500, max_dense=3500, max_neg=1000):
    """
    掃描 BDD100K 數據集，依據 ADAS 機車安全需求進行分級篩選：
    - Priority 1: 包含近距離大車 (面積比 > 12%)
    - Priority 2: 高密度多車/騎士路況 (車輛或騎士數 >= 3)
    - Priority 3: 純背景負樣本 (無車輛物體，壓制 80% 假警報)
    """
    img_dir = os.path.join(bdd_dir, split, "images")
    lab_dir = os.path.join(bdd_dir, split, "labels")

    if not os.path.isdir(img_dir) or not os.path.isdir(lab_dir):
        print(f"[-] BDD100K {split} 目錄未找到: {img_dir}")
        return []

    print(f"[*] 正在快速檢索 BDD100K ({split}) 標籤庫...", flush=True)
    all_files = [f for f in os.listdir(lab_dir) if f.endswith(".txt")]
    random.seed(42)
    random.shuffle(all_files)

    selected_large = []
    selected_dense = []
    selected_neg = []

    for i, fn in enumerate(all_files):
        if (i + 1) % 10000 == 0 or i == 0:
            print(f"    .. 掃描進度 {i + 1}/{len(all_files)} (已命中: 大車 {len(selected_large)}/{max_large}, 稠密 {len(selected_dense)}/{max_dense}, 負樣本 {len(selected_neg)}/{max_neg})", flush=True)

        lab_path = os.path.join(lab_dir, fn)
        boxes = parse_label_file(lab_path)

        base = os.path.splitext(fn)[0]
        img_fn = base + ".jpg"
        img_path = os.path.join(img_dir, img_fn)

        if len(boxes) == 0:
            if len(selected_neg) < max_neg and os.path.exists(img_path):
                selected_neg.append((img_path, lab_path, "negative"))
            continue

        has_large_vehicle = False
        valid_traffic_count = 0

        for cid, cx, cy, w, h in boxes:
            if cid in BDD_MAP:
                valid_traffic_count += 1
                mapped_cid = BDD_MAP[cid]
                area = w * h
                # 大車條件：汽車/公車/卡車且畫面佔比 >= 12%
                if mapped_cid in (2, 4) and area >= 0.12:
                    has_large_vehicle = True

        # 若完全沒有車輛/騎士/行人 (例如僅有交通號誌/天空/空路)，即為純背景負樣本！
        if valid_traffic_count == 0:
            if len(selected_neg) < max_neg and os.path.exists(img_path):
                selected_neg.append((img_path, lab_path, "negative"))
            continue

        if has_large_vehicle and len(selected_large) < max_large:
            if os.path.exists(img_path):
                selected_large.append((img_path, lab_path, "large_vehicle"))
        elif valid_traffic_count >= 3 and len(selected_dense) < max_dense:
            if os.path.exists(img_path):
                selected_dense.append((img_path, lab_path, "dense_traffic"))

        if (len(selected_large) >= max_large and 
            len(selected_dense) >= max_dense and 
            len(selected_neg) >= max_neg):
            print(f"    [!] 目標配額已提早達成，完成檢索！", flush=True)
            break

    total_selected = selected_large + selected_dense + selected_neg
    print(f"    [+] BDD100K ({split}) 篩選完成: 共 {len(total_selected)} 張", flush=True)
    print(f"        - 近距大車 (面積 > 12%): {len(selected_large)} 張", flush=True)
    print(f"        - 高密度車流與騎士: {len(selected_dense)} 張", flush=True)
    print(f"        - 純路面背景負樣本: {len(selected_neg)} 張", flush=True)
    return total_selected


def scan_tw_datasets(base_dir):
    """
    掃描現有的台灣在地化交通數據集，並修正標籤
    """
    selected_items = {"train": [], "val": []}
    for ds_name, cls_map in TW_DATASETS.items():
        ds_dir = os.path.join(base_dir, "datasets", ds_name)
        if not os.path.isdir(ds_dir):
            continue

        for split, dst_split in [("train", "train"), ("valid", "val"), ("val", "val"), ("test", "val")]:
            img_dir = os.path.join(ds_dir, split, "images")
            lab_dir = os.path.join(ds_dir, split, "labels")
            if not os.path.isdir(img_dir) or not os.path.isdir(lab_dir):
                continue

            for fn in os.listdir(lab_dir):
                if not fn.endswith(".txt"):
                    continue
                base = os.path.splitext(fn)[0]
                img_path = None
                for ext in [".jpg", ".png", ".jpeg"]:
                    candidate = os.path.join(img_dir, base + ext)
                    if os.path.exists(candidate):
                        img_path = candidate
                        break
                if img_path:
                    selected_items[dst_split].append((img_path, os.path.join(lab_dir, fn), cls_map))

    print(f"    [+] 台灣本土數據 (修正後): Train {len(selected_items['train'])} 張, Val {len(selected_items['val'])} 張")
    return selected_items


def assemble_dataset(output_dir, bdd_train_items, bdd_val_items, tw_items, dry_run=False):
    """組裝 VISOR-Titan 數據集並統計類別分佈"""
    if dry_run:
        print("\n[DRY RUN 模擬] 不實際複製檔案。")
        return

    print(f"\n[*] 正在輸出組裝數據集至: {output_dir}...")
    for split in ["train", "val"]:
        os.makedirs(os.path.join(output_dir, split, "images"), exist_ok=True)
        os.makedirs(os.path.join(output_dir, split, "labels"), exist_ok=True)

    stats = defaultdict(lambda: defaultdict(int))
    scale_stats = defaultdict(lambda: {"small": 0, "medium": 0, "large": 0})

    # 1. 處理 BDD100K 項目
    for split, items in [("train", bdd_train_items), ("val", bdd_val_items)]:
        dst_img_dir = os.path.join(output_dir, split, "images")
        dst_lab_dir = os.path.join(output_dir, split, "labels")

        for idx, (src_img, src_lab, tag) in enumerate(items):
            ext = os.path.splitext(src_img)[1]
            dst_fn = f"bdd_{split}_{idx:06d}"
            dst_img_path = os.path.join(dst_img_dir, dst_fn + ext)
            dst_lab_path = os.path.join(dst_lab_dir, dst_fn + ".txt")

            shutil.copy2(src_img, dst_img_path)

            out_lines = []
            boxes = parse_label_file(src_lab)
            for cid, cx, cy, w, h in boxes:
                if cid in BDD_MAP:
                    mapped = BDD_MAP[cid]
                    out_lines.append(f"{mapped} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")
                    stats[split][mapped] += 1
                    area = w * h
                    if area < 0.01:
                        scale_stats[split]["small"] += 1
                    elif area < 0.08:
                        scale_stats[split]["medium"] += 1
                    else:
                        scale_stats[split]["large"] += 1

            with open(dst_lab_path, "w", encoding="utf-8") as f:
                f.write("\n".join(out_lines) + ("\n" if out_lines else ""))

    # 2. 處理台灣本土數據項目 (修正大機車標籤)
    for split in ["train", "val"]:
        dst_img_dir = os.path.join(output_dir, split, "images")
        dst_lab_dir = os.path.join(output_dir, split, "labels")

        for idx, (src_img, src_lab, cls_map) in enumerate(tw_items[split]):
            ext = os.path.splitext(src_img)[1]
            dst_fn = f"tw_{split}_{idx:06d}"
            dst_img_path = os.path.join(dst_img_dir, dst_fn + ext)
            dst_lab_path = os.path.join(dst_lab_dir, dst_fn + ".txt")

            shutil.copy2(src_img, dst_img_path)

            out_lines = []
            boxes = parse_label_file(src_lab)
            for cid, cx, cy, w, h in boxes:
                if cid in cls_map:
                    mapped = cls_map[cid]
                    # 關鍵：不再執行強制改標 (保留所有近距機車標籤)
                    out_lines.append(f"{mapped} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")
                    stats[split][mapped] += 1
                    area = w * h
                    if area < 0.01:
                        scale_stats[split]["small"] += 1
                    elif area < 0.08:
                        scale_stats[split]["medium"] += 1
                    else:
                        scale_stats[split]["large"] += 1

            with open(dst_lab_path, "w", encoding="utf-8") as f:
                f.write("\n".join(out_lines) + ("\n" if out_lines else ""))

    # 3. 寫入 visor_titan.yaml
    yaml_path = os.path.join(os.path.dirname(output_dir), "visor_titan.yaml")
    rel_train = os.path.relpath(os.path.join(output_dir, "train", "images"), os.path.dirname(yaml_path)).replace("\\", "/")
    rel_val = os.path.relpath(os.path.join(output_dir, "val", "images"), os.path.dirname(yaml_path)).replace("\\", "/")

    yaml_content = f"""# V.I.S.O.R. Titan Unified Dataset Configuration (4:3 Native)
path: {os.path.abspath(output_dir).replace('\\', '/')}
train: train/images
val: val/images

nc: {len(UNIFIED_CLASSES)}
names:
"""
    for i in sorted(UNIFIED_CLASSES.keys()):
        yaml_content += f"  {i}: {UNIFIED_CLASSES[i]}\n"

    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write(yaml_content)

    print(f"[+] 數據集配置檔已生成: {yaml_path}")

    # 印出報告
    print("\n" + "=" * 60)
    print("      🎉 V.I.S.O.R. Titan 數據集組裝完成報告")
    print("=" * 60)
    for split in ["train", "val"]:
        n_imgs = len(os.listdir(os.path.join(output_dir, split, "images")))
        print(f"\n[{split.upper()}] 影像總數: {n_imgs} 張")
        print(f"  - 各類別物體標註統計:")
        for cid in sorted(UNIFIED_CLASSES.keys()):
            cname = UNIFIED_CLASSES[cid]
            cnt = stats[split][cid]
            print(f"      {cname:12s} (ID {cid}): {cnt:6d} 個")
        print(f"  - 目標尺度分佈:")
        sc = scale_stats[split]
        total_boxes = sum(sc.values()) or 1
        print(f"      小目標 (< 1%):    {sc['small']:6d} ({sc['small']/total_boxes*100:5.1f}%)")
        print(f"      中目標 (1%~8%):   {sc['medium']:6d} ({sc['medium']/total_boxes*100:5.1f}%)")
        print(f"      大目標 (> 8%):    {sc['large']:6d} ({sc['large']/total_boxes*100:5.1f}%) [大車防撞保障]")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="V.I.S.O.R. Titan Dataset Builder")
    parser.add_argument("--bdd-dir", default=r"bdd100k/bdd100k_yolo", help="Path to bdd100k_yolo")
    parser.add_argument("--tw-dir", default=r"YOLOv26_DEMO", help="Path to YOLOv26_DEMO directory")
    parser.add_argument("--out-dir", default=r"datasets/visor_titan", help="Output dataset path")
    parser.add_argument("--max-large", type=int, default=4500, help="Max BDD large vehicle images")
    parser.add_argument("--max-dense", type=int, default=3500, help="Max BDD dense traffic images")
    parser.add_argument("--max-neg", type=int, default=1000, help="Max BDD pure negative background images")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without copying files")
    args = parser.parse_args()

    print("=" * 60)
    print("  🚀 V.I.S.O.R. Titan 專屬數據集自動抽取與組裝引擎")
    print("=" * 60)

    # 1. 掃描 BDD100K Train & Val
    bdd_train = scan_bdd_dataset(args.bdd_dir, split="train", max_large=args.max_large, max_dense=args.max_dense, max_neg=args.max_neg)
    bdd_val = scan_bdd_dataset(args.bdd_dir, split="val", max_large=int(args.max_large * 0.2), max_dense=int(args.max_dense * 0.2), max_neg=int(args.max_neg * 0.2))

    # 2. 掃描台灣數據
    tw_items = scan_tw_datasets(args.tw_dir)

    # 3. 執行組裝
    assemble_dataset(args.out_dir, bdd_train, bdd_val, tw_items, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
