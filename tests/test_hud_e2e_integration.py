import asyncio
import json
import socket
import threading
import time
import os
import sys

# Add root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest.mock as mock

# Mock hardware dependencies for environment without Pi/OLED
mock_luma = mock.MagicMock()
mock_luma.__path__ = []
mock_luma_oled = mock.MagicMock()
mock_luma_oled.__path__ = []
sys.modules["luma"] = mock_luma
sys.modules["luma.core"] = mock_luma
sys.modules["luma.core.interface"] = mock_luma
sys.modules["luma.core.interface.serial"] = mock_luma
sys.modules["luma.core.render"] = mock_luma
sys.modules["luma.oled"] = mock_luma_oled
sys.modules["luma.oled.device"] = mock_luma

from main_controller import MainController
from hud.hud_client import HudClient

class MockHudClient(HudClient):
    """A HudClient that doesn't need real I2C/OLED and records received data."""
    def __init__(self, port=5005):
        # We don't call super().__init__ because we want to avoid OLED init
        self.port = port
        self.running = True
        self.data = {}
        self.last_received = 0
        self.timeout = 5.0
        self.received_payloads = []
        
        # UDP Socket (Receiver)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('127.0.0.1', self.port))
        self.sock.settimeout(0.5)
        self.device = None # No OLED

    def start(self):
        # No heartbeat thread to keep things simple
        while self.running:
            try:
                data, addr = self.sock.recvfrom(4096)
                self.data = json.loads(data.decode('utf-8'))
                self.last_received = time.time()
                self.received_payloads.append(self.data)
            except socket.timeout:
                pass
            except Exception as e:
                print(f"MockHudClient Error: {e}")

async def test_hud_e2e():
    print("--- Starting HUD E2E Integration Test ---")
    
    # 1. Setup MainController with Loopback IP
    # We'll use a dummy config for testing
    controller = MainController(demo_mode=True)
    controller.udp_broadcaster.set_target_ip('127.0.0.1') # Force loopback target
    
    # 2. Setup Mock HUD Client
    hud = MockHudClient(port=5005)
    hud_thread = threading.Thread(target=hud.start, daemon=True)
    hud_thread.start()
    
    print("2. Starting MainController...")
    controller_task = asyncio.create_task(controller.main_loop())
    
    # Wait for things to stabilize
    await asyncio.sleep(2)
    
    print("3. Injecting Threat into MainController...")
    test_warning = {
        "level": "danger",
        "message": "TEST THREAT: COLLISION ALERT",
        "dist": 2.5
    }
    
    # We'll hijack the vision_loop return value for one iteration
    # Since vision_loop is called frequently, we can just set a flag 
    # or override the method.
    original_vision_loop = controller.vision_loop
    
    async def mocked_vision_loop():
        return test_warning, None, []
    
    controller.vision_loop = mocked_vision_loop
    
    print("4. Waiting for HUD to receive threat...")
    found_threat = False
    start_time = time.time()
    while time.time() - start_time < 5.0:
        if hud.data.get("warning") and hud.data["warning"]["level"] == "danger":
            print(f"✅ HUD Received Threat: {hud.data['warning']['message']}")
            found_threat = True
            break
        await asyncio.sleep(0.1)
    
    # Restore vision loop
    controller.vision_loop = original_vision_loop
    
    print("5. Stopping Controller...")
    controller.running = False
    await controller_task
    
    hud.running = False
    hud_thread.join(timeout=1)
    
    assert found_threat, "HUD did not receive the injected threat!"
    print("✅ E2E HUD Integration Test Passed.")

if __name__ == "__main__":
    try:
        asyncio.run(test_hud_e2e())
    except Exception as e:
        print(f"❌ Test Failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
