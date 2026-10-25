import socket
import asyncio
import websockets
import json
import time
import sys

# Test Configuration
CORE_IP = "192.168.4.1"
UDP_PORT = 5005
WS_PORT = 8765
HB_PORT = 5006

async def test_websocket():
    print(f"[*] Testing WebSocket to {CORE_IP}:{WS_PORT}...")
    uri = f"ws://{CORE_IP}:{WS_PORT}"
    try:
        async with websockets.connect(uri) as websocket:
            message = await asyncio.wait_for(websocket.recv(), timeout=5)
            data = json.loads(message)
            print(f"    [OK] Received WS Data: Speed={data.get('speed')} km/h, Status={data.get('system', {}).get('pi5_status')}")
            return True
    except Exception as e:
        print(f"    [FAIL] WebSocket failed: {e}")
        return False

def test_udp_broadcast():
    print(f"[*] Testing UDP Broadcast on Port {UDP_PORT}...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.settimeout(5.0)
    try:
        sock.bind(('0.0.0.0', UDP_PORT))
        data, addr = sock.recvfrom(2048)
        payload = json.loads(data.decode())
        print(f"    [OK] Received UDP from {addr}: Speed={payload.get('speed')}")
        return True
    except Exception as e:
        print(f"    [FAIL] UDP Broadcast failed: {e}")
        return False
    finally:
        sock.close()

def test_hud_heartbeat():
    print(f"[*] Sending dummy HUD Heartbeat to {CORE_IP}:{HB_PORT}...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        payload = {"device": "TEST_TOOL", "timestamp": time.time(), "status": "active"}
        sock.sendto(json.dumps(payload).encode(), (CORE_IP, HB_PORT))
        print(f"    [OK] Heartbeat sent.")
        return True
    except Exception as e:
        print(f"    [FAIL] Heartbeat failed: {e}")
        return False
    finally:
        sock.close()

async def run_diagnostics():
    print("
--- V.I.S.O.R. System Diagnostics ---
")
    
    # 1. Network Basic
    print(f"[*] Pinging Core at {CORE_IP}...")
    # System dependent ping
    import subprocess
    ping_cmd = ["ping", "-n" if sys.platform == "win32" else "-c", "1", CORE_IP]
    if subprocess.call(ping_cmd, stdout=subprocess.DEVNULL) == 0:
        print(f"    [OK] Core is reachable.")
    else:
        print(f"    [FAIL] Core {CORE_IP} is NOT reachable. Check Wi-Fi connection.")
        return

    # 2. Communication Services
    ws_ok = await test_websocket()
    udp_ok = test_udp_broadcast()
    hb_ok = test_hud_heartbeat()

    print("
--- Result Summary ---")
    print(f"WebSocket: {'PASSED' if ws_ok else 'FAILED'}")
    print(f"UDP Broadcast: {'PASSED' if udp_ok else 'FAILED'}")
    print(f"HUD Heartbeat: {'PASSED' if hb_ok else 'FAILED'}")
    print("----------------------
")

if __name__ == "__main__":
    asyncio.run(run_diagnostics())
