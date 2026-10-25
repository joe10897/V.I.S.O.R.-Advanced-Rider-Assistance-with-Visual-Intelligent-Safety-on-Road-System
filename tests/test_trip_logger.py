import unittest
import time
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from trip_logger import TripLogger

class TestTripLogger(unittest.TestCase):
    def setUp(self):
        self.logger = TripLogger(output_dir="test_trips")

    def tearDown(self):
        self.logger.cleanup()
        if os.path.exists("test_trips"):
            for f in os.listdir("test_trips"):
                os.remove(os.path.join("test_trips", f))
            os.rmdir("test_trips")

    def test_start_log_stop(self):
        res = self.logger.start_trip(label="UnitTest")
        self.assertEqual(res["status"], "started")
        self.assertTrue(self.logger.is_logging)

        # Log steps
        self.logger.log_step({
            "speed": 45.2,
            "tilt": 12.0,
            "warning": {"level": "warning", "direction": "left", "dist": 8.5, "ttc": 1.8, "class_name": "CAR", "message": "左側車輛"},
            "lat": 25.033,
            "lng": 121.565,
            "cpu": 25.0,
            "temp": 45.0
        })

        self.logger.log_step({
            "speed": 78.5,
            "tilt": -5.0,
            "warning": {"level": "danger", "direction": "front", "dist": 3.2, "ttc": 0.8, "class_name": "BUS", "message": "前方防撞"},
            "lat": 25.034,
            "lng": 121.566,
            "cpu": 26.0,
            "temp": 46.0
        })

        time.sleep(0.6) # allow worker to flush

        summary = self.logger.stop_trip()
        self.assertEqual(summary["status"], "stopped")
        self.assertEqual(summary["records_count"], 2)
        self.assertEqual(summary["max_speed_kmh"], 78.5)
        self.assertEqual(summary["events_fcw"], 1)
        self.assertEqual(summary["events_bsd"], 1)
        self.assertEqual(summary["events_danger"], 1)
        self.assertTrue(os.path.exists(summary["file"]))
        self.assertTrue(os.path.exists(summary["thesis_report_path"]))

    def test_detections_and_thesis_report(self):
        res = self.logger.start_trip(label="ThesisPerceptionTest")
        self.assertEqual(res["status"], "started")

        # Step 1: 3 scooters, 1 car, 1 bus
        self.logger.log_step({
            "speed": 52.0,
            "tilt": -2.0,
            "fps": 24.5,
            "detections": [
                {"class": "scooter", "distance": 4.5, "camera": "front"},
                {"class": "scooter", "distance": 6.2, "camera": "rear"},
                {"class": "motorcycle", "distance": 8.0, "camera": "rear"},
                {"class": "car", "distance": 12.0, "camera": "front"},
                {"class": "bus", "distance": 15.5, "camera": "front"}
            ],
            "warning": {"level": "none", "direction": "none"}
        })

        # Step 2: 2 cars, 1 pedestrian
        self.logger.log_step({
            "speed": 48.0,
            "tilt": 1.5,
            "fps": 25.0,
            "detections": [
                {"class": "car", "distance": 7.5, "camera": "rear"},
                {"class": "car", "distance": 9.0, "camera": "front"},
                {"class": "pedestrian", "distance": 3.8, "camera": "front"}
            ],
            "warning": {"level": "warning", "direction": "left", "dist": 7.5, "class_name": "CAR"}
        })

        time.sleep(0.6)
        summary = self.logger.stop_trip()

        self.assertEqual(summary["total_records"], 2)
        self.assertEqual(summary["total_detections"], 8)
        self.assertEqual(summary["det_scooters"], 3)
        self.assertEqual(summary["det_cars"], 3)
        self.assertEqual(summary["det_buses"], 1)
        self.assertEqual(summary["det_pedestrians"], 1)
        self.assertEqual(summary["det_front"], 5)
        self.assertEqual(summary["det_rear"], 3)
        self.assertAlmostEqual(summary["min_threat_dist_m"], 3.8, places=1)
        self.assertTrue(os.path.exists(summary["thesis_report_path"]))

        # 檢驗生成的論文報告內容包含 YOLOv26 與 LaTeX 表格
        with open(summary["thesis_report_path"], "r", encoding="utf-8") as f:
            report_text = f.read()
            self.assertIn("YOLOv26 TW Titan", report_text)
            self.assertIn("\\begin{table}", report_text)
            self.assertIn("機車 / 二輪車輛", report_text)

if __name__ == "__main__":
    unittest.main()

