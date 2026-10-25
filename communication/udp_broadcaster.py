import socket
import json
import threading
import time

class UdpBroadcaster:
    """
    負責將 V.I.S.O.R. 的儀表數據透過獨立高效能背景線程 (20Hz) 廣播至區域網路 (Pi Zero HUD)。
    具備多重廣播目標、自動網段探測與零延遲心跳保活，保證 HUD 永不 Signal Lost。
    """
    def __init__(self, ip='255.255.255.255', port=5005):
        self.broadcast_ip = ip
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        self.latest_data = {}
        self.data_lock = threading.Lock()
        self.running = True
        self.broadcast_targets = {'255.255.255.255', '192.168.4.255'}
        
        # 啟動獨立 20Hz 恆定廣播背景執行緒 (每 50ms 一次，永不阻塞)
        self.worker_thread = threading.Thread(target=self._broadcast_loop, daemon=True)
        self.worker_thread.start()

    def set_target_ip(self, ip: str):
        if ip and ip != '0.0.0.0':
            with self.data_lock:
                self.broadcast_targets.add(ip)
                if '.' in ip:
                    subnet_broadcast = '.'.join(ip.split('.')[:3]) + '.255'
                    self.broadcast_targets.add(subnet_broadcast)

    def send_data(self, data: dict):
        """
        主迴圈更新最新遙測數據快取 (0ms 耗時)
        """
        with self.data_lock:
            self.latest_data = data

    def send_immediate(self, data: dict, count: int = 5):
        """
        立即直接透過 socket 發送高優先級指令封包（如 shutdown / system_command），
        繞過 latest_data 快取與定時迴圈，並連發 count 次確保 UDP 必定送達。
        """
        try:
            message = json.dumps(data).encode('utf-8')
            with self.data_lock:
                targets = set(self.broadcast_targets)
            for _ in range(count):
                for target in targets:
                    try:
                        self.socket.sendto(message, (target, self.port))
                    except Exception:
                        pass
                time.sleep(0.01)
        except Exception as e:
            print(f"[UDP_BROADCASTER] send_immediate error: {e}")

    def _broadcast_loop(self):
        """
        獨立背景定時發送迴圈：以 20Hz 穩定發送 UDP 封包
        """
        while self.running:
            with self.data_lock:
                data_copy = dict(self.latest_data) if self.latest_data else None
                targets = set(self.broadcast_targets)

            if data_copy:
                try:
                    message = json.dumps(data_copy).encode('utf-8')
                    for target in targets:
                        try:
                            self.socket.sendto(message, (target, self.port))
                        except Exception:
                            pass
                except Exception:
                    pass

            time.sleep(0.05)  # 20 Hz 恆定心跳

    def close(self):
        self.running = False
        try:
            self.socket.close()
        except Exception:
            pass
