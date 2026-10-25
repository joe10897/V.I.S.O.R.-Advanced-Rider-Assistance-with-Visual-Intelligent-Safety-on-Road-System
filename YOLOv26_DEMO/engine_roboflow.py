from inference_sdk import InferenceHTTPClient
import cv2
import numpy as np

class RoboflowTaiwanEngine:
    def __init__(self, api_key="q9bHnZFXARoDEzr2iwGc"):
        self.client = InferenceHTTPClient(
            api_url="https://serverless.roboflow.com",
            api_key=api_key
        )
        # 定義要使用的模型 ID
        self.model_traffic = "taiwan-traffic-dataset-v2.0/3"
        self.model_blindspot = "blind-spot-detection-tjabj/3"
        
        # 類別映射 (歸一化為 VISOR 標準)
        self.class_map = {
            "car": "car",
            "truck": "truck",
            "motor": "scooter",
            "scooter": "scooter",
            "person": "pedestrian",
            "pedestrian": "pedestrian",
            "helmet": "helmet"
        }

    def infer(self, frame_path):
        """
        同時呼叫兩個模型並融合結果
        """
        # 1. 呼叫台灣交通模型
        res_t = self.client.infer(frame_path, model_id=self.model_traffic)
        # 2. 呼叫盲區偵測模型
        res_b = self.client.infer(frame_path, model_id=self.model_blindspot)
        
        combined_results = []
        
        # 處理模型 1 的結果
        for pred in res_t.get('predictions', []):
            combined_results.append(self._format_pred(pred))
            
        # 處理模型 2 的結果
        for pred in res_b.get('predictions', []):
            # 避免重複偵測 (簡單的 BBox 重疊檢查可以在此實作)
            combined_results.append(self._format_pred(pred))
            
        return combined_results

    def _format_pred(self, pred):
        # Roboflow 回傳的是中心點格式 (x, y, width, height)
        # 轉換為 [x1, y1, x2, y2]
        x, y, w, h = pred['x'], pred['y'], pred['width'], pred['height']
        x1, y1 = int(x - w/2), int(y - h/2)
        x2, y2 = int(x + w/2), int(y + h/2)
        
        raw_class = pred['class']
        return {
            "bbox": [x1, y1, x2, y2],
            "class": self.class_map.get(raw_class, raw_class),
            "conf": pred['confidence']
        }

if __name__ == "__main__":
    # 測試腳本
    engine = RoboflowTaiwanEngine()
    print("Roboflow Dual-Model Engine Initialized.")
    # result = engine.infer("test_taiwan_road.jpg")
    # print(result)
