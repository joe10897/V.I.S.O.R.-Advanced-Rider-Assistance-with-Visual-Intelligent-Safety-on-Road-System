import os
import unittest

class TestSetupAP(unittest.TestCase):
    def test_setup_ap_exists(self):
        self.assertTrue(os.path.exists("scripts/setup_ap.sh"), "setup_ap.sh script should exist")

    def test_setup_ap_content(self):
        if not os.path.exists("scripts/setup_ap.sh"):
            self.skipTest("Script doesn't exist yet")
        
        with open("scripts/setup_ap.sh", "r") as f:
            content = f.read()
            self.assertIn("VISOR_Net", content, "SSID should be VISOR_Net")
            self.assertIn("192.168.4.1/24", content, "IP should be 192.168.4.1/24")
            self.assertIn("nmcli", content, "Should use nmcli for configuration")

if __name__ == "__main__":
    unittest.main()
