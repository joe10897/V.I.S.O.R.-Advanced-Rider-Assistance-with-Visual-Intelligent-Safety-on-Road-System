import socket
import time
import json
import random

def simulate_hud_heartbeat():
    host = '127.0.0.1' # Localhost for testing, usually broadcast or specific IP
    port = 5006
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    print(f"HUD Simulator started. Sending heartbeats to {host}:{port}...")
    
    try:
        while True:
            payload = {
                "device": "PiZero_HUD",
                "status": "active",
                "timestamp": time.time(),
                "battery": random.randint(80, 100)
            }
            msg = json.dumps(payload).encode('utf-8')
            sock.sendto(msg, (host, port))
            print(".", end='', flush=True)
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\nHUD Simulator stopped.")
    finally:
        sock.close()

if __name__ == "__main__":
    simulate_hud_heartbeat()

