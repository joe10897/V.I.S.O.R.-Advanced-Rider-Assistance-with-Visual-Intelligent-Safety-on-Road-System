import unittest
import os
import sys
import time
import numpy as np
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

class TestRoadReadyIntegration(unittest.TestCase):
    @patch('main_controller.FrameReader')
    @patch('main_controller.VisorCore')
    @patch('main_controller.VisorBluetoothServer')
    @patch('main_controller.VisorWebSocketServer')
    @patch('main_controller.UdpBroadcaster')
    @patch('main_controller.UdpListener')
    def setUp(self, mock_udp_l, mock_udp_b, mock_ws, mock_bt, mock_visor, mock_fr):
        from main_controller import MainController
        self.controller = MainController()
        # Mock camera frames
        self.controller.last_frame_front = np.zeros((480, 640, 3), dtype=np.uint8)
        self.controller.last_frame_rear = np.zeros((480, 640, 3), dtype=np.uint8)
        self.controller.last_ai_results = (None, None, [{"class": "car", "bbox": [100, 100, 200, 200], "distance": 12.5}])

    def tearDown(self):
        if hasattr(self.controller, 'trip_logger'):
            self.controller.trip_logger.cleanup()

    def test_telemetry_sync_command(self):
        # 1. Test Telemetry Sync Uplink
        cmd = {
            "action": "telemetry_sync",
            "telemetry": {
                "speed": 62.5,
                "tilt": 14.0,
                "lat": 25.033,
                "lng": 121.565,
                "heading": 88.0
            }
        }
        self.controller.handle_command(cmd)
        self.assertIsNotNone(self.controller.phone_telemetry)
        self.assertEqual(self.controller.phone_telemetry["speed"], 62.5)
        self.assertEqual(self.controller.phone_telemetry["tilt"], 14.0)

    def test_trip_logger_lifecycle(self):
        # 2. Test Start Trip Log
        self.controller.handle_command({"action": "start_trip_log", "label": "TestRoad"})
        self.assertTrue(self.controller.trip_logger.is_logging)

        # Log a dummy step
        self.controller.trip_logger.log_step({
            "speed": 55.0,
            "tilt": 12.0,
            "warning": {"level": "danger", "direction": "right", "dist": 3.5, "class_name": "CAR"},
            "speed_source": "phone_gps"
        })

        # 3. Test Stop Trip Log
        self.controller.handle_command({"action": "stop_trip_log"})
        self.assertFalse(self.controller.trip_logger.is_logging)
        # Verify bt_server broadcast was called with trip_summary
        calls = self.controller.bt_server.broadcast.call_args_list
        summary_payloads = [c[0][0] for c in calls if isinstance(c[0][0], dict) and c[0][0].get("type") == "trip_summary"]
        self.assertTrue(len(summary_payloads) > 0)
        summary = summary_payloads[0]["summary"]
        self.assertGreaterEqual(summary["total_records"], 1)
        self.assertEqual(summary["total_alerts"], 2)

    def test_calibration_frame_generator(self):
        # 4. Test Bluetooth Calibration Frame (240x180 JPEG base64)
        calib_cmd = {
            "action": "get_calibration_frame",
            "camera": "front",
            "width": 240,
            "height": 180,
            "quality": 50
        }
        self.controller.handle_command(calib_cmd)
        calls = self.controller.bt_server.broadcast.call_args_list
        calib_payloads = [c[0][0] for c in calls if isinstance(c[0][0], dict) and c[0][0].get("type") == "calibration_frame"]
        self.assertTrue(len(calib_payloads) > 0)
        calib = calib_payloads[0]
        self.assertEqual(calib.get("camera"), "front")
        img_data = calib.get("data") or calib.get("image")
        self.assertTrue(img_data.startswith("data:image/jpeg;base64,"))
        self.assertLess(len(img_data), 12000)

    def test_hud_pulse_test(self):
        # 5. Test HUD Pulse Test Trigger
        self.controller.handle_command({"action": "test_hud_pulse"})
        # Should not crash and spawns worker
        self.assertTrue(True)

if __name__ == "__main__":
    unittest.main()
