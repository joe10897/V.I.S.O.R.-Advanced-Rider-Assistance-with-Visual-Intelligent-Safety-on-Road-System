import cv2
import time
import os
import glob
import base64
import threading
from collections import deque

class DashcamRecorder:
    """
    V.I.S.O.R. 雙鏡頭行車記錄與一鍵快照引擎
    - 支援一鍵雙鏡頭高解析度拍照 (Snapshot)
    - 支援連續循環行車錄影 (Continuous Dashcam REC)
    - 支援事件/哨兵預錄機制 (Pre-event Sentry Buffer)
    - 支援 APP 快照相簿清單與縮圖/大圖即時傳輸 (Base64 Gallery)
    - 異步後台存檔，零阻塞 AI 視覺推論
    """
    def __init__(self, fps=15.0, width=640, height=480, output_base="recordings"):
        self.fps = fps
        self.width = width
        self.height = height
        self.output_base = output_base
        
        self.snapshot_dir = os.path.join(output_base, "snapshots")
        self.video_dir = os.path.join(output_base, "videos")
        self.sentry_dir = os.path.join(output_base, "events")
        
        for d in [self.snapshot_dir, self.video_dir, self.sentry_dir]:
            os.makedirs(d, exist_ok=True)
            
        self.is_recording = False
        self.rec_start_time = None
        self.video_writer = None
        
        # 哨兵預錄緩衝區 (5秒)
        self.pre_event_buffer = deque(maxlen=int(fps * 5))
        self.sentry_writer = None
        self.sentry_frames_left = 0
        
        self.lock = threading.Lock()
        self._last_snapshot_files = []

    def take_snapshot(self, frame_front=None, frame_rear=None):
        """
        異步執行一鍵拍照，儲存當前雙鏡頭畫面為高畫質 JPEG
        """
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        saved_files = []

        def _save_worker(f_front, f_rear, ts):
            try:
                if f_front is not None:
                    name_f = f"FRONT_{ts}.jpg"
                    path_f = os.path.join(self.snapshot_dir, name_f)
                    cv2.imwrite(path_f, f_front, [cv2.IMWRITE_JPEG_QUALITY, 95])
                    print(f"[RECORDER] 前鏡頭快照已儲存: {path_f}")
                if f_rear is not None:
                    name_r = f"REAR_{ts}.jpg"
                    path_r = os.path.join(self.snapshot_dir, name_r)
                    cv2.imwrite(path_r, f_rear, [cv2.IMWRITE_JPEG_QUALITY, 95])
                    print(f"[RECORDER] 後鏡頭快照已儲存: {path_r}")
            except Exception as e:
                print(f"[ERROR] 快照儲存失敗: {e}")

        f_front_copy = frame_front.copy() if frame_front is not None else None
        f_rear_copy = frame_rear.copy() if frame_rear is not None else None
        
        if f_front_copy is not None: saved_files.append(f"FRONT_{timestamp}.jpg")
        if f_rear_copy is not None: saved_files.append(f"REAR_{timestamp}.jpg")
        
        thread = threading.Thread(target=_save_worker, args=(f_front_copy, f_rear_copy, timestamp), daemon=True)
        thread.start()
        
        return saved_files

    def list_snapshots(self):
        """
        列出 snapshots 資料夾中所有快照檔案清單 (依時間最新降序排列)
        """
        items = []
        try:
            pattern = os.path.join(self.snapshot_dir, "*.jpg")
            files = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)
            for f in files:
                fname = os.path.basename(f)
                stat = os.stat(f)
                cam_type = "FRONT" if fname.startswith("FRONT") else "REAR"
                mtime_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime))
                items.append({
                    "name": fname,
                    "cam": cam_type,
                    "time": mtime_str,
                    "size_kb": round(stat.st_size / 1024, 1)
                })
        except Exception as e:
            print(f"[RECORDER] 列出快照失敗: {e}")
        return items

    def get_snapshot_base64(self, filename, max_width=240):
        """
        讀取指定快照檔案，並轉為低延遲壓縮 Base64 字串供 APP 渲染 (藍牙極速模式，約 4KB~6KB)
        """
        try:
            filepath = os.path.join(self.snapshot_dir, os.path.basename(filename))
            if not os.path.exists(filepath):
                return None
            img = cv2.imread(filepath)
            if img is None:
                return None
            
            # 等比例縮小以便在藍牙極速傳輸 (約 4KB~6KB，0.05秒即可送達)
            h, w = img.shape[:2]
            if w > max_width:
                scale = max_width / float(w)
                img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
            
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 55]
            _, buffer = cv2.imencode('.jpg', img, encode_param)
            b64_str = base64.b64encode(buffer).decode('utf-8')
            return f"data:image/jpeg;base64,{b64_str}"
        except Exception as e:
            print(f"[RECORDER] 快照編碼失敗: {e}")
            return None

    def delete_snapshot(self, filename):
        """
        刪除指定快照
        """
        try:
            filepath = os.path.join(self.snapshot_dir, os.path.basename(filename))
            if os.path.exists(filepath):
                os.remove(filepath)
                print(f"[RECORDER] 已刪除快照: {filepath}")
                return True
        except Exception as e:
            print(f"[ERROR] 刪除快照失敗: {e}")
        return False

    def toggle_recording(self, force_state=None):
        """
        切換連續錄影狀態
        """
        with self.lock:
            target_state = not self.is_recording if force_state is None else force_state
            if target_state == self.is_recording:
                return self.is_recording
            
            if target_state:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                filename = os.path.join(self.video_dir, f"DASHCAM_{timestamp}.mp4")
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                self.video_writer = cv2.VideoWriter(filename, fourcc, self.fps, (self.width, self.height))
                
                if self.video_writer.isOpened():
                    self.is_recording = True
                    self.rec_start_time = time.time()
                    print(f"[RECORDER] [REC] 行車錄影開始: {filename}")
                else:
                    self.video_writer = None
                    self.is_recording = False
                    print(f"[ERROR] 無法開啟行車錄影寫入器: {filename}")
            else:
                if self.video_writer:
                    self.video_writer.release()
                    self.video_writer = None
                self.is_recording = False
                self.rec_start_time = None
                print("[RECORDER] [STOP] 行車錄影已停止並存檔。")
                
            return self.is_recording

    def add_frame(self, frame):
        """
        注入最新即時畫面至連續錄影器與哨兵緩衝區
        """
        if frame is None:
            return
        
        with self.lock:
            self.pre_event_buffer.append(frame.copy())
            
            if self.is_recording and self.video_writer:
                try:
                    self.video_writer.write(frame)
                except Exception as e:
                    print(f"[RECORDER] 錄影寫入異常: {e}")
                    
            if self.sentry_writer and self.sentry_frames_left > 0:
                try:
                    self.sentry_writer.write(frame)
                    self.sentry_frames_left -= 1
                    if self.sentry_frames_left <= 0:
                        self.sentry_writer.release()
                        self.sentry_writer = None
                        print("[RECORDER] 哨兵事件錄影完成。")
                except Exception:
                    pass

    def trigger_sentry_event(self, post_event_secs=10):
        """
        觸發異常震動/碰撞哨兵錄影 (包含事發前5秒)
        """
        with self.lock:
            if self.sentry_writer:
                self.sentry_frames_left = max(self.sentry_frames_left, int(self.fps * post_event_secs))
                return
            
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(self.sentry_dir, f"SENTRY_{timestamp}.mp4")
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            self.sentry_writer = cv2.VideoWriter(filename, fourcc, self.fps, (self.width, self.height))
            
            if not self.sentry_writer.isOpened():
                self.sentry_writer = None
                return None
            
            for f in self.pre_event_buffer:
                self.sentry_writer.write(f)
                
            self.sentry_frames_left = int(self.fps * post_event_secs)
            print(f"[RECORDER] [WARN] 哨兵事件觸發存檔: {filename}")
            return filename

    # Alias for backwards compatibility
    trigger_event = trigger_sentry_event

    def cleanup(self):
        with self.lock:
            if self.video_writer:
                self.video_writer.release()
                self.video_writer = None
            if self.sentry_writer:
                self.sentry_writer.release()
                self.sentry_writer = None
            self.is_recording = False
            self.pre_event_buffer.clear()
