import unittest
import json
import os
import sys

# Add root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils_config import load_config
from main_controller import MainController

class TestConfig(unittest.TestCase):
    def setUp(self):
        # Backup original config if exists
        if os.path.exists("config.json"):
            with open("config.json", "r") as f:
                self.original_config = f.read()
        else:
            self.original_config = None

    def tearDown(self):
        # Restore original config
        if self.original_config:
            with open("config.json", "w") as f:
                f.write(self.original_config)
        elif os.path.exists("config.json"):
            os.remove("config.json")

    def test_load_defaults(self):
        # Test loading when file doesn't exist (simulated by using a non-existent path)
        config = load_config("non_existent_config.json")
        self.assertEqual(config['network']['udp_port'], 5005)

    def test_custom_config(self):
        # Create a custom config
        custom_data = {
            "network": {
                "udp_port": 9999
            },
            "thresholds": {
                "danger_dist": 1.0
            }
        }
        with open("config.json", "w") as f:
            json.dump(custom_data, f)
            
        config = load_config("config.json")
        self.assertEqual(config['network']['udp_port'], 9999)
        self.assertEqual(config['thresholds']['danger_dist'], 1.0)
        # Check default value preservation
        self.assertEqual(config['network']['broadcast_ip'], "255.255.255.255") 

    def test_main_controller_init(self):
        # Test if MainController reads the config
        # Use a real file for FrameReader to succeed
        import glob
        samples = glob.glob("sample_videos/*.mp4")
        if not samples:
             self.skipTest("No sample videos found for test")
        
        valid_video = samples[0]

        custom_data = {
            "vision": {
                "source": None,
                "model_path": "yolov8n.pt",
                "device": "cpu",
                "focal_length": 800,
                "conf_threshold": 0.25
            },
            "system": {
                "hud_timeout": 10.0
            }
        }
        with open("config.json", "w") as f:
            json.dump(custom_data, f)
            
        controller = MainController(video_source=valid_video)
        self.assertEqual(controller.hud_timeout, 10.0)
        # Clean up controller resources
        controller.frame_reader.stop()
        controller.udp_listener.stop()
        controller.udp_broadcaster.close()


if __name__ == '__main__':
    unittest.main()
