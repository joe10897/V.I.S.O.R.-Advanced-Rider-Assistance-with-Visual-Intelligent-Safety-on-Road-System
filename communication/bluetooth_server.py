import json
import threading
import time
import socket
import queue
import os
import subprocess

class VisorBluetoothServer:
    """
    V.I.S.O.R. 原生藍牙通訊伺服器 (Native RFCOMM / SPP) - 強化抗斷訊與零執行緒洩漏架構
    1. 指令佇列化非同步執行 (Command Queue Worker)：
       徹底杜絕過去每秒 4 次建立系統 OS 執行緒 (4Hz telemetry_sync)，運行 10 分鐘產生 2,400+ 執行緒導致 Linux 核心資源耗盡 (Thread Exhaustion / Resource temporarily unavailable) 之嚴重缺陷。
    2. 原子化分塊傳輸與硬體防堵塞 (Atomic Chunking & Congestion Watchdog)：
       512 位元組平滑分塊寫入，若傳輸逾時具備健全回退機制，確保換行符號完整閉合，杜絕 JSON 粘包損壞。
       若連續逾時具備自我復原重置能力。
    3. 遙測平滑限速與高優先級插隊：
       一般遙測平滑限速約 4.5Hz，避免擠爆 RFCOMM 基頻緩衝區；快照與校正畫面則以最高優先級即時推播。
    """
    def __init__(self, name="VISOR_Core", channel=1):
        self.name = name
        self.channel = channel
        self.server_sock = None
        self.client_sock = None
        self.client_addr = None
        self.running = False
        self.client_connected = False
        self.command_callback = None
        self.send_queue = queue.Queue(maxsize=30)
        self.command_queue = queue.Queue(maxsize=30)
        self.receiver_thread = None
        self.sender_thread = None
        self.cmd_worker_thread = None
        self._last_telemetry_time = 0.0

    def start(self):
        print(f"[INFO] 啟動原生藍牙 RFCOMM 伺服器 (頻道 {self.channel}, 名稱: {self.name})...")
        
        # 確保免螢幕自動配對代理人運行 (無接螢幕時自動批准配對碼，支援 Pixel 7a 等新手機)
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            agent_path = os.path.join(base_dir, "visor_bt_agent.py")
            if os.path.exists(agent_path):
                subprocess.Popen(["python3", agent_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print("[BT] 藍牙免螢幕自動配對代理人已在背景運作 (NoInputNoOutput)")
        except Exception:
            pass

        self.running = True
        self.cmd_worker_thread = threading.Thread(target=self._command_worker, daemon=True)
        self.cmd_worker_thread.start()
        self.receiver_thread = threading.Thread(target=self._run_server, daemon=True)
        self.receiver_thread.start()
        self.sender_thread = threading.Thread(target=self._send_worker, daemon=True)
        self.sender_thread.start()

    def _command_worker(self):
        """專屬單一指令工作執行緒：依序非同步處理手機指令，完全不建立額外系統執行緒"""
        while self.running:
            try:
                cmd = self.command_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            
            try:
                if self.command_callback:
                    self.command_callback(cmd)
            except Exception as e:
                print(f"[BT] 指令執行異常: {e}")

    def _run_server(self):
        while self.running:
            try:
                if hasattr(socket, 'AF_BLUETOOTH') and hasattr(socket, 'BTPROTO_RFCOMM'):
                    if self.server_sock:
                        try: self.server_sock.close()
                        except: pass

                    self.server_sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
                    self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    
                    bind_addr = "00:00:00:00:00:00"
                    bound = False
                    for ch in [self.channel, 1, 2, 3]:
                        try:
                            self.server_sock.bind((bind_addr, ch))
                            self.channel = ch
                            bound = True
                            break
                        except OSError as b_err:
                            if b_err.errno == 98: # Address already in use
                                time.sleep(0.5)
                                continue
                            else:
                                raise b_err

                    if not bound:
                        time.sleep(1.5)
                        continue

                    self.server_sock.listen(1)
                    print(f"[BT] 藍牙序列埠伺服器監聽中 (頻道 {self.channel})，等待手機連線...")

                    while self.running:
                        try:
                            client_sock, client_info = self.server_sock.accept()
                            self.client_sock = client_sock
                            self.client_addr = client_info
                            self.client_sock.settimeout(2.0)
                            self.client_connected = True
                            print(f"[BT] 📱 手機已透過藍牙連線！裝置位址: {client_info}")

                            buffer = ""
                            while self.running and self.client_connected:
                                try:
                                    data = self.client_sock.recv(1024)
                                    if not data:
                                        break
                                    buffer += data.decode('utf-8', errors='replace')
                                    lines = buffer.split('\n')
                                    buffer = lines.pop()
                                    for line in lines:
                                        line = line.strip()
                                        if line and self.command_callback:
                                            try:
                                                parsed = json.loads(line)
                                                # 推入單一指令工作佇列，杜絕頻繁 thread 建立導致系統當機
                                                if self.command_queue.full():
                                                    try: self.command_queue.get_nowait()
                                                    except queue.Empty: pass
                                                self.command_queue.put_nowait(parsed)
                                            except Exception as parse_e:
                                                print(f"[BT] 指令格式錯誤: {parse_e}")
                                except (socket.timeout, TimeoutError):
                                    # 手機純接收遙測未發送指令時超時為正常現象，繼續保持連線
                                    continue
                                except Exception as rx_e:
                                    if self.running and self.client_connected:
                                        print(f"[BT] 接收異常中斷: {rx_e}")
                                    break

                            print("[BT] 手機藍牙連線已斷開。")
                            self.client_connected = False
                            try:
                                if self.client_sock: self.client_sock.close()
                            except Exception: pass
                            self.client_sock = None
                        except Exception:
                            if self.running:
                                self.client_connected = False
                                time.sleep(0.5)
                else:
                    print("[WARN] 本機 Python 不支援 AF_BLUETOOTH，進入模擬模式。")
                    time.sleep(5)
            except Exception:
                if self.running:
                    time.sleep(2)

    def _send_worker(self):
        """專屬後台發送執行緒，負責將佇列中的資料安全發送至藍牙 Socket"""
        consecutive_timeouts = 0
        while self.running:
            try:
                payload = self.send_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if self.client_connected and self.client_sock:
                try:
                    data = (json.dumps(payload) + "\n").encode('utf-8')
                    chunk_size = 512
                    total_sent = 0
                    start_tx = time.time()
                    
                    while total_sent < len(data) and self.client_connected:
                        try:
                            sent = self.client_sock.send(data[total_sent:total_sent + chunk_size])
                            if sent == 0:
                                raise ConnectionResetError("BT socket sent 0 bytes")
                            total_sent += sent
                            consecutive_timeouts = 0
                            if len(data) > 1024:
                                time.sleep(0.003) # 釋放時間槽讓 RFCOMM 緩衝區平滑清空
                        except (socket.timeout, TimeoutError):
                            # 單次 chunk 逾時：檢查總傳輸時間是否已超標 (> 2.5 秒)
                            if time.time() - start_tx > 2.5:
                                consecutive_timeouts += 1
                                print(f"[BT] 單封包傳輸嚴重堵塞 (>2.5s)，補齊換行符號以維持封包分界")
                                try:
                                    self.client_sock.send(b"\n")
                                except Exception:
                                    pass
                                break
                            time.sleep(0.01)
                            continue

                    if consecutive_timeouts >= 3:
                        print(f"[BT] 藍牙連續發送逾時 {consecutive_timeouts} 次，鏈路死結，主動重置連線")
                        raise TimeoutError("Consecutive RFCOMM timeouts")

                except Exception as tx_e:
                    print(f"[BT] 發送封包中斷或逾時: {tx_e}")
                    self.client_connected = False
                    try:
                        if self.client_sock: self.client_sock.close()
                    except Exception: pass
                    self.client_sock = None
                    # 清理積壓佇列
                    while not self.send_queue.empty():
                        try: self.send_queue.get_nowait()
                        except: break

    def broadcast(self, payload):
        """
        零阻塞廣播：將封包推入非同步佇列，0ms 立即返回
        """
        if not self.client_connected:
            return

        is_priority = payload.get("type") in [
            "snapshot_list", "snapshot_image", "calibration_frame", 
            "trip_summary", "trip_status", "trip_logs_list", "notification", "pong"
        ] or payload.get("alert") == 1
        
        # 針對藍牙 SPP 頻寬進行遙測平滑限速 (約 4.5Hz)，高優先級通知、校正圖與照片則 100% 立即發送
        if not is_priority:
            now = time.time()
            if now - self._last_telemetry_time < 0.22:
                return
            self._last_telemetry_time = now

        try:
            if is_priority:
                # 高優先級封包 (照片、校正圖、通知) 確保推入；若佇列滿則擠掉最舊的一筆一般遙測
                if self.send_queue.full():
                    try:
                        self.send_queue.get_nowait()
                    except queue.Empty:
                        pass
                self.send_queue.put(payload, timeout=0.1)
            else:
                # 一般遙測：佇列滿時直接替換最舊的一筆，絕不阻塞
                if self.send_queue.full():
                    try:
                        self.send_queue.get_nowait()
                    except queue.Empty:
                        pass
                self.send_queue.put_nowait(payload)
        except Exception:
            pass

    def stop(self):
        self.running = False
        self.client_connected = False
        if self.client_sock:
            try: self.client_sock.close()
            except: pass
        if self.server_sock:
            try: self.server_sock.close()
            except: pass
        print("[INFO] 藍牙伺服器已停止。")
