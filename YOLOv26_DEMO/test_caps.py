import cv2
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine_yolo26 import TaiwanTrafficEngine
from spatial_fusion import SpatialFusion

# Test different distance caps on f0ace550 video to compare threat counts
eng = TaiwanTrafficEngine()
video_path = r"C:\Users\USER\Desktop\motorcycle_assist\sample_videos\f0ace550-ad5d-424a-8c45-6999318bcd10.mp4"

configs = [
    {
        "name": "Strict (Current: 2m/4m/8m)",
        "caps": {"critical": 2.0, "warning": 4.0, "caution": 8.0},
    },
    {
        "name": "Medium (3m/6m/12m)",
        "caps": {"critical": 3.0, "warning": 6.0, "caution": 12.0},
    },
    {
        "name": "Moderate (5m/10m/15m)",
        "caps": {"critical": 5.0, "warning": 10.0, "caution": 15.0},
    },
    {
        "name": "Generous (8m/15m/25m)",
        "caps": {"critical": 8.0, "warning": 15.0, "caution": 25.0},
    },
]


def test_config(cap_cfg):
    cap = cv2.VideoCapture(video_path)
    fusion = SpatialFusion()

    # Override thresholds inside fusion dynamically for this test
    # (since they are referenced in process() as constants, we will override them or simulate)
    # Actually, we can just run the test by temporarily modifying the constants in the module
    import spatial_fusion

    spatial_fusion.TTC_CRITICAL = 1.0
    spatial_fusion.TTC_WARNING = 1.5
    spatial_fusion.TTC_CAUTION = 2.5

    # We will modify the caps in spatial_fusion.py or manually run the logic here
    crit, warn, caut, safe = 0, 0, 0, 0
    frames = 0

    while cap.isOpened() and frames < 300:
        ret, frame = cap.read()
        if not ret:
            break
        frames += 1
        h, w = frame.shape[:2]
        dets = eng.infer(frame, conf=0.15)

        # Custom process logic with custom caps
        # We simulate spatial_fusion.process but with custom caps
        res = fusion.process(dets, {}, (h, w))
        for r in res:
            dist = r["distance"]
            ttc = r["ttc"]
            # Recompute threat level with custom caps
            # Assume IN_LANE or UNKNOWN uses these caps
            lvl = "safe"
            if r["rel_speed"] > 0.5:  # closing
                if ttc < 1.0 and dist < cap_cfg["caps"]["critical"]:
                    lvl = "critical"
                elif ttc < 1.5 and dist < cap_cfg["caps"]["warning"]:
                    lvl = "warning"
                elif ttc < 2.5 and dist < cap_cfg["caps"]["caution"]:
                    lvl = "caution"

            if lvl == "critical":
                crit += 1
            elif lvl == "warning":
                warn += 1
            elif lvl == "caution":
                caut += 1
            else:
                safe += 1

    cap.release()
    print(
        f"{cap_cfg['name']}: critical={crit} | warning={warn} | caution={caut} | safe={safe}"
    )


for cfg in configs:
    test_config(cfg)
