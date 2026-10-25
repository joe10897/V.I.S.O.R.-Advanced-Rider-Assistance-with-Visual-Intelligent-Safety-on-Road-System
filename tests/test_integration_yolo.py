import asyncio
import os
import sys

# Add root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main_controller import MainController

async def test_run():
    # Use a specific video file
    video_path = "sample_videos/sample1.mp4"
    if not os.path.exists(video_path):
        print(f"Video not found: {video_path}")
        return

    print("Initializing MainController...")
    controller = MainController(video_source=video_path)
    
    # Start the controller in a separate task
    task = asyncio.create_task(controller.main_loop())
    
    print("Running for 15 seconds...")
    await asyncio.sleep(15)
    
    print("Stopping...")
    controller.running = False
    await task
    print("Test Complete.")

if __name__ == "__main__":
    asyncio.run(test_run())
