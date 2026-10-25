import os
from roboflow import Roboflow
import yaml

ROBOFLOW_API_KEY = "q9bHnZFXARoDEzr2iwGc"

def download_datasets():
    if ROBOFLOW_API_KEY == "YOUR_API_KEY_HERE":
        print("[ERROR] 請先填入你的 Roboflow API Key！")
        return

    rf = Roboflow(api_key=ROBOFLOW_API_KEY)
    
    # 建立下載目錄
    os.makedirs("YOLOv26_DEMO/datasets", exist_ok=True)
    os.chdir("YOLOv26_DEMO/datasets")

    # 1. 下載 Taiwan Traffic Dataset v2.0
    print("Downloading Taiwan Traffic Dataset...")
    project1 = rf.workspace("hanhan27").project("taiwan-traffic-dataset-v2.0")
    dataset1 = project1.version(3).download("yolov8")

    # 2. 下載 Blind Spot Detection
    print("Downloading Blind Spot Detection Dataset...")
    project2 = rf.workspace("attackurankle").project("blind-spot-detection-tjabj")
    dataset2 = project2.version(3).download("yolov8")

    print("\n[SUCCESS] 資料集下載完成。")
    print("手動建議：請將兩個資料集的圖片與標籤合併，並修改 data.yaml 中的類別映射。")

if __name__ == "__main__":
    download_datasets()
