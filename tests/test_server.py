import asyncio
import os
import sys

# Add root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main_controller import MainController

async def run_server():
    video_path = "sample_videos/sample1.mp4"
    if not os.path.exists(video_path):
        # Fallback to any mp4
        import glob
        files = glob.glob("sample_videos/*.mp4")
        if files:
            video_path = files[0]
        else:
            print("No video found")
            return

    print(f"Starting server with {video_path}...")
    controller = MainController(video_source=video_path)
    
    server_task = asyncio.create_task(controller.main_loop())
    
    # Run for 60 seconds
    try:
        await asyncio.sleep(60)
    except asyncio.CancelledError:
        pass
    finally:
        controller.running = False
        await server_task

if __name__ == "__main__":
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        pass
