import asyncio
import socket
import json
import websockets
import argparse
import sys

def udp_listener(port=5005):
    """
    模擬 HUD：監聽 UDP 廣播。
    """
    print(f"HUD Simulator listening on UDP port {port}...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('', port))
    
    try:
        while True:
            data, addr = sock.recvfrom(1024)
            try:
                message = json.loads(data.decode('utf-8'))
                print(f"[HUD] Received from {addr}: {message}")
            except json.JSONDecodeError:
                print(f"[HUD] Received raw data: {data}")
    except KeyboardInterrupt:
        print("\nStopping HUD Simulator...")
    finally:
        sock.close()

async def ws_client(uri):
    """
    模擬 App：連接 WebSocket Server。
    """
    print(f"App Simulator connecting to {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            print("[App] Connected!")
            
            # Send a test command
            await websocket.send("Hello from App Simulator")
            
            async for message in websocket:
                try:
                    data = json.loads(message)
                    print(f"[App] Received: {data}")
                except json.JSONDecodeError:
                    print(f"[App] Received raw: {message}")
    except Exception as e:
        print(f"[App] Error: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="V.I.S.O.R. Test Clients")
    parser.add_argument('mode', choices=['hud', 'app'], help="Mode to run: 'hud' (UDP listener) or 'app' (WebSocket client)")
    parser.add_argument('--ip', default='127.0.0.1', help="Server IP for App mode (default: 127.0.0.1)")
    parser.add_argument('--port', type=int, help="Port (default: 5005 for HUD, 8765 for App)")

    args = parser.parse_args()

    if args.mode == 'hud':
        port = args.port if args.port else 5005
        udp_listener(port)
    elif args.mode == 'app':
        port = args.port if args.port else 8765
        uri = f"ws://{args.ip}:{port}"
        try:
            asyncio.run(ws_client(uri))
        except KeyboardInterrupt:
            print("\nStopping App Simulator...")
