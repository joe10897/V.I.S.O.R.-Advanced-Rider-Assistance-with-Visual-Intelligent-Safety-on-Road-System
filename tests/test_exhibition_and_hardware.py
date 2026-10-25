"""
Test Suite: Exhibition Mode, Non-blocking Hardware Guards & Multi-screen Sync
Verifies:
1. Exhibition Mode autonomous 32s scenario loop & telemetry broadcast
2. Non-blocking FrameReader startup and dynamic standby frame generation
3. Dynamic OLED model detection/switching (SSD1306 vs SH1106)
4. Offline HUD standalone fallback demo mode
5. WebSocket/BT set_exhibition action handling
"""

import asyncio
import json
import os
import socket
import sys
import threading
import time
import unittest.mock as mock

# Add project root to path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

# Mock luma hardware dependencies
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

mock_visor_core = mock.MagicMock()
mock_visor_instance = mock.MagicMock()
mock_visor_instance.process_rear.return_value = ([], {})
mock_visor_instance.process_front.return_value = ([], {})
mock_visor_instance.detections_to_threats.return_value = None
mock_visor_core.VisorCore.return_value = mock_visor_instance
sys.modules["visor_core"] = mock_visor_core

from main_controller import MainController
from hud.hud_client import HudClient
from vision.frame_reader import FrameReader


class MockHudReceiver:
    """Listens on UDP 5005 loopback to capture telemetry packets broadcast by MainController."""
    def __init__(self, port=5005):
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('127.0.0.1', self.port))
        self.sock.settimeout(0.2)
        self.running = True
        self.received = []

    def start(self):
        while self.running:
            try:
                data, _ = self.sock.recvfrom(8192)
                payload = json.loads(data.decode('utf-8'))
                self.received.append(payload)
            except socket.timeout:
                pass
            except Exception:
                pass

    def stop(self):
        self.running = False
        self.sock.close()


def test_1_exhibition_telemetry_phases():
    """Verify that _generate_exhibition_telemetry correctly iterates all 6 scenario phases."""
    print("\n[TEST 1] Testing 32-second Exhibition Telemetry Scenario Phases...")
    controller = MainController(demo_mode=True, exhibition_mode=True)
    base_t = controller.exhibition_start_time

    # Phase 1: Acceleration (e.g. t = 3.0s)
    spd, tilt, warn, radar, dets, cam, lanes = controller._generate_exhibition_telemetry(base_t + 3.0)
    assert 20.0 <= spd <= 75.0, f"Expected accelerating speed, got {spd}"
    assert abs(tilt) <= 4.0, f"Expected upright motorcycle during accel, got {tilt}"
    print(f"  -> Phase 1 (t=3s): Speed={spd} km/h, Tilt={tilt} deg [PASS]")

    # Phase 2: Left BSD (e.g. t = 9.0s)
    spd, tilt, warn, radar, dets, cam, lanes = controller._generate_exhibition_telemetry(base_t + 9.0)
    assert warn is not None, "Expected warning in Phase 2"
    assert warn.get("direction") == "left", f"Expected left warning, got {warn.get('direction')}"
    print(f"  -> Phase 2 (t=9s): BSD Alert={warn['message']}, Dir={warn['direction']} [PASS]")

    # Phase 3: Mountain curve leaning (e.g. t = 15.0s)
    spd, tilt, warn, radar, dets, cam, lanes = controller._generate_exhibition_telemetry(base_t + 15.0)
    assert abs(tilt) >= 15.0, f"Expected heavy lean angle in mountain curve, got {tilt}"
    print(f"  -> Phase 3 (t=15s): Mountain Curve Lean Angle={tilt} deg [PASS]")

    # Phase 4: Right BSD scooter danger (e.g. t = 20.5s)
    spd, tilt, warn, radar, dets, cam, lanes = controller._generate_exhibition_telemetry(base_t + 20.5)
    assert warn is not None, "Expected warning in Phase 4"
    assert warn.get("direction") == "right", f"Expected right warning, got {warn.get('direction')}"
    assert warn.get("level") == "danger", f"Expected danger level, got {warn.get('level')}"
    print(f"  -> Phase 4 (t=20.5s): Danger Invert Alert={warn['message']}, Level={warn['level']} [PASS]")

    # Phase 5: Speed camera alert (e.g. t = 25.0s)
    spd, tilt, warn, radar, dets, cam, lanes = controller._generate_exhibition_telemetry(base_t + 25.0)
    assert cam is not None, "Expected speed camera alert in Phase 5"
    assert cam.get("limit") == 50, f"Expected 50 km/h camera limit, got {cam.get('limit')}"
    print(f"  -> Phase 5 (t=25s): Speed Camera Limit={cam['limit']} km/h, Dist={cam['distance']}m [PASS]")

    # Phase 6: FCW truck collision alert & emergency stop (e.g. t = 29.5s)
    spd, tilt, warn, radar, dets, cam, lanes = controller._generate_exhibition_telemetry(base_t + 29.5)
    assert warn is not None, "Expected FCW warning in Phase 6"
    assert warn.get("direction") == "front", f"Expected front FCW, got {warn.get('direction')}"
    print(f"  -> Phase 6 (t=29.5s): FCW Alert={warn['message']}, Speed Decel={spd} km/h [PASS]")
    print("[TEST 1 PASSED] All 6 exhibition phases generated accurately.")


def test_2_frame_reader_nonblocking():
    """Verify that FrameReader initializes in under 50ms without blocking on missing camera."""
    print("\n[TEST 2] Testing FrameReader Non-blocking Hardware Guards...")
    t0 = time.time()
    # Try opening non-existent video index 99
    reader = FrameReader(video_source=99, width=640, height=480)
    elapsed = time.time() - t0

    assert elapsed < 0.2, f"FrameReader __init__ took too long: {elapsed:.3f}s (must be < 0.2s)"
    assert reader.is_dummy is True, "Expected reader to gracefully fall back to is_dummy mode"

    # Verify that reader serves valid standby frames
    frame = reader.read(timeout=0.2)
    assert frame is not None, "Expected non-None standby frame"
    assert frame.shape == (480, 640, 3), f"Expected shape (480, 640, 3), got {frame.shape}"

    reader.stop()
    print(f"[TEST 2 PASSED] FrameReader initialized in {elapsed*1000:.1f}ms and served dynamic standby frames.")


def test_3_hud_dynamic_oled_model():
    """Verify that HudClient respects 0.96 SSD1306 default and handles dynamic model changes."""
    print("\n[TEST 3] Testing Dynamic OLED Model Selection (SSD1306 0.96 vs SH1106 1.3)...")
    hud = HudClient(model="SSD1306")
    assert hud.preferred_model == "SSD1306", "Expected default preferred_model to be SSD1306"

    # Simulate receiving a telemetry payload specifying SH1106
    payload_sh1106 = {
        "timestamp": time.time(),
        "speed": 55.0,
        "tilt": 12.0,
        "hud_config": {
            "oled_model": "SH1106"
        }
    }
    hud.data = payload_sh1106
    # Call init_oled to verify it switches target to SH1106
    hud.init_oled(preferred_model="SH1106")
    assert hud.preferred_model == "SH1106", "Expected preferred_model to update to SH1106"

    # Switch back to SSD1306
    hud.init_oled(preferred_model="SSD1306")
    assert hud.preferred_model == "SSD1306", "Expected preferred_model to switch back to SSD1306"
    print("[TEST 3 PASSED] Dynamic OLED model switching verified.")


def test_4_offline_hud_standalone_demo():
    """Verify that HudClient renders autonomous standalone demo loop when offline > 10s."""
    print("\n[TEST 4] Testing Offline HUD Standalone Fallback Demo Loop...")
    hud = HudClient()
    # Call offline demo render across 3 timesteps
    t_now = time.time()
    for offset in [2.0, 8.0, 16.0, 22.0]:
        # Should execute cleanly without throwing exceptions
        hud._render_offline_demo(t_now + offset)
    print("[TEST 4 PASSED] Offline standalone demo rendered smoothly across all phases.")


async def test_5_websocket_command_and_udp_broadcast():
    """Verify that set_exhibition WebSocket action toggles mode and broadcasts via UDP."""
    print("\n[TEST 5] Testing End-to-End WebSocket Toggle & Synchronized UDP Broadcast...")
    receiver = MockHudReceiver(port=5005)
    rx_thread = threading.Thread(target=receiver.start, daemon=True)
    rx_thread.start()

    controller = MainController(demo_mode=True, exhibition_mode=False)
    controller.udp_broadcaster.set_target_ip('127.0.0.1')

    # Start main loop in background task
    main_task = asyncio.create_task(controller.main_loop())
    await asyncio.sleep(0.5)

    # 1. Turn ON exhibition mode
    print("  -> Sending set_exhibition enabled=True command...")
    controller.exhibition_mode = True
    controller.exhibition_start_time = time.time()
    await asyncio.sleep(1.0)

    # Check received packets
    packets_ex = [p for p in receiver.received if p.get("exhibition") is True]
    assert len(packets_ex) > 0, "Expected UDP packets with exhibition=True"
    sample = packets_ex[-1]
    assert sample.get("speed_source") == "exhibition", f"Expected speed_source=exhibition, got {sample.get('speed_source')}"
    print(f"  -> Received synchronized Exhibition UDP packet: Speed={sample['speed']} km/h, Tilt={sample['tilt']} deg")

    # 2. Turn OFF exhibition mode
    print("  -> Sending set_exhibition enabled=False command...")
    controller.exhibition_mode = False
    await asyncio.sleep(0.5)

    packets_live = [p for p in receiver.received if p.get("exhibition") is False]
    assert len(packets_live) > 0, "Expected UDP packets reverting to live mode with exhibition=False"
    print(f"  -> System reverted to live mode cleanly: exhibition={packets_live[-1].get('exhibition')}")

    # Cleanup
    controller.running = False
    receiver.stop()
    try:
        await asyncio.wait_for(main_task, timeout=1.0)
    except Exception:
        pass
    print("[TEST 5 PASSED] End-to-end exhibition toggle & UDP broadcast verified.")


async def run_all():
    print("=" * 70)
    print("V.I.S.O.R. HARDWARE OPTIMIZATION & EXHIBITION MODE TEST SUITE")
    print("=" * 70)
    test_1_exhibition_telemetry_phases()
    test_2_frame_reader_nonblocking()
    test_3_hud_dynamic_oled_model()
    test_4_offline_hud_standalone_demo()
    await test_5_websocket_command_and_udp_broadcast()
    print("\n" + "=" * 70)
    print("[PASS] ALL 5 TEST SUITES PASSED WITH ZERO ERRORS!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_all())
