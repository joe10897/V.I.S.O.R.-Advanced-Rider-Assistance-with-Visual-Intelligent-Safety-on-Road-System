import socket
import threading
import json
import time

class UdpListener:
    """
    負責監聽來自區域網路的 UDP 封包 (例如 HUD 的心跳)。
    """
    def __init__(self, port=5006):
        self.port = port
        self.running = False
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Allow multiple sockets to bind to this port (useful for development)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.socket.bind(('0.0.0.0', self.port))
            print(f"[INFO] UDP Listener bound to port {self.port}")
        except Exception as e:
            print(f"[ERROR] UDP Bind failed: {e}")

        self.latest_data = {}
        self.last_received_time = 0
        self.last_addr = None
        self.thread = threading.Thread(target=self._listen_loop, daemon=True)

    def start(self):
        self.running = True
        self.thread.start()

    def _listen_loop(self):
        while self.running:
            try:
                # Non-blocking check or timeout
                self.socket.settimeout(1.0)
                data, addr = self.socket.recvfrom(1024)
                
                try:
                    payload = json.loads(data.decode('utf-8'))
                    self.latest_data = payload
                    self.last_received_time = time.time()
                    if addr and addr[0]:
                        self.last_addr = addr[0]
                    # print(f"[DEBUG] Heartbeat from {addr}: {payload}")
                except json.JSONDecodeError:
                    pass
                    
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"[ERROR] UDP Listen Error: {e}")
                break

    def get_last_heartbeat(self):
        return self.last_received_time, self.latest_data, self.last_addr

    def stop(self):
        self.running = False
        self.socket.close()
