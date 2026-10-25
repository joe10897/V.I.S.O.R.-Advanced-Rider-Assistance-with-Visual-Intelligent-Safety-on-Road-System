import cv2, time, os, threading, queue
from vision.detector import Detector, Detection
from vision.sensor_sim import SensorSim
from vision.fusion import Fusion
from vision.tracker import CentroidTracker
from vision.utils import draw_label

# A dedicated class to read frames from a video source in a separate thread
class FrameReader:
    def __init__(self, video_source):
        self.video_source = video_source
        self.cap = cv2.VideoCapture(video_source)
        if not self.cap.isOpened():
            raise IOError("Cannot open video source")
        # Use a queue to store frames, with a max size of 1 to always get the latest frame
        self.q = queue.Queue(maxsize=1)
        self.stopped = False
        self.thread = threading.Thread(target=self.run, daemon=True)

    def start(self):
        self.thread.start()

    def run(self):
        while not self.stopped:
            if not self.q.full():
                ret, frame = self.cap.read()
                if not ret:
                    print("[INFO] Stream ended or connection lost. Attempting to reconnect...")
                    self.reconnect()
                    continue
                self.q.put(frame)
            else:
                # If queue is full, it means processing is lagging behind.
                # We can sleep for a short time to yield CPU.
                time.sleep(0.01)
    
    def reconnect(self):
        self.cap.release()
        while not self.stopped and not self.cap.isOpened():
            self.cap = cv2.VideoCapture(self.video_source)
            time.sleep(1)
        if self.cap.isOpened():
            print("[INFO] Reconnected.")

    def get_frame_properties(self):
        width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        return width, height

    def stop(self):
        self.stopped = True
        # Wait for the thread to finish
        if self.thread.is_alive():
            self.thread.join(timeout=1)
        self.cap.release()

def main(video_path=None, device='cpu', save_output=True):
    url = "https://cctvn.freeway.gov.tw/abs2mjpg/bmjpg?camera=13310"
    video_source = url if video_path is None else video_path

    try:
        frame_reader = FrameReader(video_source)
    except IOError as e:
        print(f"Error: {e}")
        return

    width, height = frame_reader.get_frame_properties()
    detector = Detector(model_name='yolov8n.pt', device=device)
    sensor = SensorSim()
    fusion = Fusion(width, height)
    tracker = CentroidTracker()

    output_writer = None
    if save_output:
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        output_writer = cv2.VideoWriter('output_demo.mp4', fourcc, 20.0, (width, height))
        print("[INFO] Output video will be saved as output_demo.mp4")

    frame_reader.start()
    print("[INFO] Frame reader started in a separate thread.")

    start_time = time.time()
    last_time = start_time
    while True:
        try:
            # Get the latest frame from the queue. This is non-blocking with a timeout.
            frame = frame_reader.q.get(timeout=1.0)
        except queue.Empty:
            # If the queue is empty for a while, the source might be dead.
            if not frame_reader.thread.is_alive():
                print("[INFO] Frame reader thread has stopped.")
                break
            print("[INFO] Waiting for frame...")
            continue

        dt = time.time() - last_time
        sens = sensor.step(dt if dt>0 else 0.1)
        last_time = time.time()

        # Pre-process frame for better night-time visibility
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        cl = clahe.apply(l)
        limg = cv2.merge((cl,a,b))
        processed_frame = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)

        # Define classes of interest from COCO dataset
        # 0: person, 2: car, 3: motorcycle
        CLASSES_OF_INTEREST = [2, 3]
        CONF_THRESHOLD = 0.25

        dets = detector.detect(processed_frame)
        dets_filtered = [d for d in dets if d.class_id in CLASSES_OF_INTEREST and d.confidence > CONF_THRESHOLD]
        rects = [d.bbox for d in dets_filtered]
        
        # Update the tracker and get currently tracked objects
        tracked_objects = tracker.update(rects)

        # Create a mapping from bbox to detection object for easy lookup
        bbox_to_det = {tuple(d.bbox): d for d in dets_filtered}

        # Loop over the tracked objects to apply fusion logic
        for objectID, centroid in tracked_objects.items():
            # Get the latest bbox from the tracker's history for this ID
            if not tracker.bbox_history.get(objectID):
                continue
            
            latest_bbox = tracker.bbox_history[objectID][-1]
            det = bbox_to_det.get(tuple(latest_bbox))

            if det is None:
                continue

            class_name = detector.model.names[det.class_id]
            bbox_history = tracker.bbox_history[objectID]
            
            x1, y1, x2, y2 = det.bbox
            threat_level, dist = fusion.classify_threat(det, class_name, bbox_history)

            if threat_level == 'DANGEROUSLY_CLOSE':
                # Red Alert
                draw_label(frame, f'DANGER! {dist:.1f}m', (x1, y1 - 5), bg=(0, 0, 255))
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                print('\a', end='') # Sound alert
            elif threat_level == 'IN_LANE_APPROACHING':
                # Yellow Alert for in-lane objects that are close
                draw_label(frame, f'IN-LANE APPROACHING! {dist:.1f}m', (x1, y1 - 5), bg=(0, 220, 255))
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 2)
            elif threat_level == 'SIDE_APPROACHING':
                # Yellow Alert for side objects that are looming
                draw_label(frame, f'SIDE LOOMING! {dist:.1f}m', (x1, y1 - 5), bg=(0, 200, 200))
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 2)
            elif fusion.is_in_lane(det):
                # Green Label for in-lane objects without threat
                label = f'{class_name} {dist:.1f}m'
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                draw_label(frame, label, (x1, y1 - 5))
            # Objects that are not in lane and not a threat are not drawn

        if fusion.is_tilt_alert(sens):
            draw_label(frame, 'TILT ALERT!', (20, 40), bg=(0, 0, 255))

        cv2.putText(frame, f"Speed(km/h): {sens['speed_kmh']:.1f}", (20, height-60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255),1)
        cv2.putText(frame, f"Tilt(deg): {sens['tilt_deg']:.1f}", (20, height-35), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255),1)

        # Show the frame and save it if needed
        cv2.imshow('Motorcycle Assist Demo', frame)
        if output_writer:
            output_writer.write(frame)

        # Exit on 'q' or 'ESC'
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == 27:
            break

    print("[INFO] Cleaning up...")
    frame_reader.stop()
    if output_writer:
        output_writer.release()
    cv2.destroyAllWindows()
    print("[INFO] Done.")

if __name__ == '__main__':
    print("請選擇輸入來源：")
    print("1. 網絡串流")
    print("2. 本地影片檔案")
    
    choice = input("請輸入您的選擇 (1 or 2): ")
    
    video_path = None
    if choice == '1':
        print("您選擇了網絡串流。")
        # video_path remains None to use the default URL in main()
    elif choice == '2':
        print("您選擇了本地影片檔案。")
        sample_dir = 'sample_videos'
        try:
            video_files = [f for f in os.listdir(sample_dir) if f.endswith('.mp4')]
            if not video_files:
                print(f"在 '{sample_dir}' 資料夾中找不到任何 .mp4 檔案。")
                exit()
            
            print("請選擇要處理的影片檔案：")
            for i, filename in enumerate(video_files):
                print(f"{i+1}. {filename}")
            
            file_choice = int(input(f"請輸入檔案編號 (1-{len(video_files)}): "))
            if 1 <= file_choice <= len(video_files):
                video_path = os.path.join(sample_dir, video_files[file_choice-1])
            else:
                print("無效的檔案選擇。")
                exit()
        except FileNotFoundError:
            print(f"錯誤：找不到 '{sample_dir}' 資料夾。")
            exit()
    else:
        print("無效的選擇。")
        exit()
        
    main(video_path=video_path, device='cpu', save_output=True)
