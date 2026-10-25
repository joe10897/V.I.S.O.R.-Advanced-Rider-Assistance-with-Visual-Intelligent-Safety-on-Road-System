#!/usr/bin/env python3
# ==============================================================================
#  V.I.S.O.R. Titan Training Suite (RTX 5060 Dedicated Edition)
#  專為 RTX 5060 訓練機打造的旗艦級訓練腳本：
#  - 全局 4:3 矩形原生訓練：imgsz=(480, 640), rect=True (0% 黑邊浪費)
#  - ADAS 專屬增強調教：mosaic=0.4, close_mosaic=15, scale=0.5
#  - 遷移學習保護：freeze=10 (保留 Backbone 泛化特徵，微調檢測頭)
#  - 支援 SSH 遠端背景執行 (tmux / nohup)
# ==============================================================================

import os
import sys
import shutil
import argparse
from ultralytics import YOLO

# Windows / Linux utf-8 console safety
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

def parse_args():
    parser = argparse.ArgumentParser(description="V.I.S.O.R. Titan RTX 5060 Training Suite")
    parser.add_argument("--data", default="datasets/visor_titan.yaml", help="Path to data.yaml")
    parser.add_argument("--base-model", default="models/yolo26n.pt", help="Pretrained weights path")
    parser.add_argument("--epochs", type=int, default=120, help="Total training epochs")
    parser.add_argument("--batch", type=int, default=32, help="Batch size for RTX 5060")
    parser.add_argument("--device", default="0", help="CUDA device index or '0,1' for dual GPU")
    parser.add_argument("--imgsz", nargs="+", type=int, default=[480, 640], help="Training resolution [H, W]")
    parser.add_argument("--freeze", type=int, default=10, help="Freeze backbone layers (default: 10)")
    parser.add_argument("--project", default="runs/visor_titan_5060", help="Training run directory")
    parser.add_argument("--name", default="yolo26n_titan_v1", help="Experiment name")
    return parser.parse_args()

def main():
    args = parse_args()
    
    # 確保基本權重存在
    base_model = args.base_model
    if not os.path.exists(base_model):
        candidates = [
            "yolo26n.pt",
            "models/yolo26n.pt",
            "YOLOv26_DEMO/models/yolo26n.pt",
            "YOLOv26_DEMO/yolo26n.pt"
        ]
        for c in candidates:
            if os.path.exists(c):
                base_model = c
                break

    train_imgsz = tuple(args.imgsz) if len(args.imgsz) > 1 else args.imgsz[0]

    print("=" * 65)
    print("  🚀 V.I.S.O.R. Titan 旗艦級訓練啟動 (RTX 5060 專用)")
    print("=" * 65)
    print(f"  - 數據設定檔: {args.data}")
    print(f"  - 預訓練基底: {base_model}")
    print(f"  - 訓練解析度: {train_imgsz} (4:3 矩形原生無黑邊)")
    print(f"  - 批次大小:   {args.batch} (RTX 5060 加速)")
    print(f"  - 訓練輪數:   {args.epochs} 輪 (最後 15 輪停用 Mosaic)")
    print(f"  - 骨幹凍結:   前 {args.freeze} 層 (避免災難性遺忘)")
    print("=" * 65, flush=True)

    if not os.path.exists(args.data):
        print(f"[-] 錯誤：找不到數據設定檔 {args.data}！")
        print("    請先執行: python tools/build_visor_titan.py 組裝數據集。")
        sys.exit(1)

    model = YOLO(base_model)

    results = model.train(
        data=args.data,
        epochs=args.epochs,
        imgsz=train_imgsz,
        rect=True,              # 4:3 矩形訓練，徹底消滅黑邊
        batch=args.batch,
        device=args.device,
        optimizer="auto",
        lr0=0.003,             # 平滑遷移微調學習率
        lrf=0.01,
        scale=0.5,             # 尺度擾動 (0.5x ~ 1.5x)
        mosaic=0.4,            # 適度 Mosaic，保留 60% 原尺寸大車
        copy_paste=0.15,
        close_mosaic=15,       # 收斂期關閉 Mosaic，直面乾淨大車
        freeze=args.freeze,    # 凍結前 10 層 Backbone
        degrees=5,
        translate=0.1,
        fliplr=0.5,
        erasing=0.2,
        patience=20,           # Early stopping
        pretrained=True,
        project=args.project,
        name=args.name,
        exist_ok=True,
        seed=42,
        verbose=True
    )

    best_weights = os.path.join(str(results.save_dir), "weights", "best.pt")
    target_deploy = "models/yolo26n_tw_titan.pt"
    os.makedirs(os.path.dirname(target_deploy), exist_ok=True)

    if os.path.exists(best_weights):
        shutil.copy2(best_weights, target_deploy)
        print("\n" + "=" * 65)
        print("  🎉 訓練圓滿完成！")
        print(f"  - 最優權重位置: {best_weights}")
        print(f"  - 自動部署位置: {target_deploy}")
        print("=" * 65)
        print("\n[部署至 Pi 5 指令]:")
        print(f"  python deploy_to_pi5.py 192.168.4.1\n")
    else:
        print(f"[!] 訓練完成，但未找到 {best_weights}")

if __name__ == "__main__":
    main()
