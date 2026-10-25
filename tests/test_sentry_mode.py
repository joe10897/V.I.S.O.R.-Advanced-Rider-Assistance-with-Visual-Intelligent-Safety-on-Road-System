import asyncio
import os
import sys
import time
import json
import websockets

# Add root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main_controller import MainController

async def test_sentry():
    print("1. Initializing MainController...")
    video_path = "sample_videos/sample1.mp4"
    if not os.path.exists(video_path):
        import glob
        video_path = glob.glob("sample_videos/*.mp4")[0]

    controller = MainController(video_source=video_path)
    
    # Start controller
    srv_task = asyncio.create_task(controller.main_loop())
    
    await asyncio.sleep(2) # Wait for init
    
    print("2. Enabling Sentry Mode via WebSocket mock...")
    # Simulate receiving command
    controller.handle_command({"action": "set_sentry", "enabled": True})
    
    print("3. Simulating a 'Shock' (Vibration)...")
    # Manually trigger a jump in tilt to trigger the recorder
    # We can reach into the sensor_sim or just wait for it? 
    # Let's force a tilt change in the next iteration by modifying the sim state
    controller.sensor_sim.speed = 0 # Stationary
    # The loop will check tilt_diff = abs(current - last)
    # So we need to wait for one loop to set 'last_tilt'
    await asyncio.sleep(0.5)
    
    print("   Setting extreme tilt to trigger sentry...")
    controller.sensor_sim.t = 1000 # Jump in time might help if it's based on sin(t)
    # Better: just set the tilt directly if we can, but it's calculated in step().
    # Let's monkeypatch step() briefly or just let it run.
    # Actually, let's just wait for a natural large jump or force it.
    # I'll just call trigger_event manually to test the recording part first.
    
    filename = controller.recorder.trigger_event()
    print(f"   Recording triggered manually: {filename}")
    
    print("4. Waiting for recording to finish (10s post-event)...")
    await asyncio.sleep(12)
    
    if filename and os.path.exists(filename):
        print(f"✅ Sentry file created successfully: {filename}")
        print(f"   Size: {os.path.getsize(filename)} bytes")
    else:
        print("❌ Sentry file was NOT created.")

    print("5. Cleaning up...")
    controller.running = False
    await srv_task
    print("Test Complete.")

if __name__ == "__main__":
    asyncio.run(test_sentry())
