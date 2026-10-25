import asyncio
import websockets
import json

async def check_visor():
    uri = "ws://pi5:8765"
    try:
        async with websockets.connect(uri) as websocket:
            message = await asyncio.wait_for(websocket.recv(), timeout=2)
            data = json.loads(message)
            print("System Status:")
            print(json.dumps(data.get("system", {}), indent=2))
            
            if "ai_results" in data:
                print("\n[SUCCESS] Camera data is being processed.")
                # If there are no detections, it might be because the scene is static
                # But the fact that 'ai_results' exists and is a list means the detector is running
                print(f"Current detections: {data['ai_results']}")
                
    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(check_visor())
