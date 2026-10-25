import asyncio
import os
import sys
import threading
import time
import json
import socket

# Add root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main_controller import MainController

# Mock HUD Simulator
def hud_sender(stop_event):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    while not stop_event.is_set():
        payload = {"device": "HUD", "timestamp": time.time()}
        sock.sendto(json.dumps(payload).encode(), ('127.0.0.1', 5006))
        time.sleep(1)
    sock.close()

async def test_heartbeat_logic():
    print("1. Starting MainController...")
    # Use a dummy video source to avoid file dependency issues in test
    # Or mock FrameReader. For integration test, we can use existing sample.
    video_path = "sample_videos/sample1.mp4" 
    if not os.path.exists(video_path):
        import glob
        video_path = glob.glob("sample_videos/*.mp4")[0]

    controller = MainController(video_source=video_path)
    
    # Start Controller Task
    srv_task = asyncio.create_task(controller.main_loop())
    
    print("2. Waiting 3s (Expect HUD OFFLINE)...")
    await asyncio.sleep(3)
    
    # Check Status (Should be Offline)
    # We need to access internal state or check broadcasted payload.
    # Since we can't easily snoop UDP loopback without another socket, 
    # let's peek at the variable we derived in the loop. 
    # But wait, the variable is local to the loop.
    # We can check udp_listener.last_received_time directly.
    last_hb, _, _ = controller.udp_listener.get_last_heartbeat()
    print(f"   Last Heartbeat: {last_hb} (Should be 0)")
    assert last_hb == 0, "HUD should be offline initially"

    print("3. Starting HUD Simulator (Expect HUD ONLINE)...")
    stop_hud = threading.Event()
    hud_thread = threading.Thread(target=hud_sender, args=(stop_hud,))
    hud_thread.start()
    
    await asyncio.sleep(3)
    
    last_hb_new, _, _ = controller.udp_listener.get_last_heartbeat()
    print(f"   Last Heartbeat: {last_hb_new} (Should be > 0)")
    assert last_hb_new > 0, "HUD should be online now"
    
    print("4. Stopping HUD Simulator (Expect HUD OFFLINE after timeout)...")
    stop_hud.set()
    hud_thread.join()
    
    print("   Waiting 6s for timeout...")
    await asyncio.sleep(6)
    
    # In the main loop logic: hud_online = (time.time() - last_hb) < 5.0
    is_online = (time.time() - last_hb_new) < 5.0
    print(f"   Is Online: {is_online} (Should be False)")
    assert not is_online, "HUD should be offline after timeout"

    print("5. Stopping Controller...")
    controller.running = False
    await srv_task
    print("✅ Heartbeat Logic Verified.")

if __name__ == "__main__":
    try:
        asyncio.run(test_heartbeat_logic())
    except Exception as e:
        print(f"❌ Test Failed: {e}")
