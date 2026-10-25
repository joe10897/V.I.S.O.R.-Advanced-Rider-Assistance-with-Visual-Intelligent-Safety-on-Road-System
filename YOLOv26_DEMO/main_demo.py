import cv2
import time
import numpy as np
import os
import sys
import argparse
import torch
from engine_ufld import UFLDv2Engine
from spatial_fusion import SpatialFusion
from visualizer_hud import VisualizerHUD

def resolve_video_path(video_arg):
    if os.path.exists(video_arg):
        return video_arg
    candidate = os.path.join(os.path.dirname(__file__), "..", "sample_videos", video_arg)
    if os.path.exists(candidate):
        return os.path.abspath(candidate)
    return video_arg

def main():
    parser = argparse.ArgumentParser(description="V.I.S.O.R. Demo")
    parser.add_argument("--video", default=r"C:\Users\USER\Desktop\motorcycle_assist\sample_videos\f0ace550-ad5d-424a-8c45-6999318bcd10.mp4")
    parser.add_argument("--roboflow", action="store_true", help="Use Roboflow API instead of local YOLOv26")
    parser.add_argument("--no-display", action="store_true", help="Force headless (write video only)")
    parser.add_argument("--max-frames", type=int, default=0, help="Limit number of frames to process")
    parser.add_argument("--skip", type=int, default=2, help="Skip N frames for lane detection (0=no skip, 2=every 3rd)")
    parser.add_argument("--lane-fp16", action="store_true", help="Use FP16 UFLD model (faster, half size)")
    parser.add_argument("--lane-model", default="cv_magnet", choices=["cv_magnet", "ufld", "lstr"], help="Lane detection model (default: cv_magnet)")
    parser.add_argument("--device", default="cuda:0" if torch.cuda.is_available() else "cpu", help="Compute device for YOLO (default: auto)")
    parser.add_argument("--imgsz", nargs="+", type=int, default=[288, 384], help="YOLO inference resolution (default: 288 384)")
    parser.add_argument("--scale", type=float, default=1.0, help="Input frame downscale (e.g. 0.5 = 640x360)")
    parser.add_argument("--no-lane", action="store_true", help="Skip lane detection (use for rear camera)")
    parser.add_argument("--output", "-o", default=None, help="Output MP4 file path (e.g. result.mp4)")
    parser.add_argument("--yolo-model", "--weights", default="yolo26n_tw_titan.onnx", help="YOLO model path or name (default: yolo26n_tw_titan.onnx)")
    args = parser.parse_args()

    use_yolo26 = not args.roboflow

    if use_yolo26:
        from engine_yolo26 import TaiwanTrafficEngine
        model_path = args.yolo_model
        if model_path and not os.path.exists(model_path):
            candidates = [
                os.path.join(os.path.dirname(__file__), "models", model_path),
                os.path.join(os.path.dirname(__file__), model_path),
                os.path.join(os.path.dirname(__file__), "..", model_path),
                os.path.join(os.path.dirname(__file__), "..", "models", model_path),
            ]
            for c in candidates:
                if os.path.exists(c):
                    model_path = os.path.abspath(c)
                    break
        infer_imgsz = tuple(args.imgsz) if len(args.imgsz) > 1 else args.imgsz[0]
        detector = TaiwanTrafficEngine(model_path=model_path, device=args.device, imgsz=infer_imgsz, rect=True)
        mode_str = f"YOLOv26 ({os.path.basename(model_path) if model_path else 'yolo26n_tw_titan.onnx'}, {args.device})"
    else:
        from engine_roboflow import RoboflowTaiwanEngine
        detector = RoboflowTaiwanEngine(api_key="q9bHnZFXARoDEzr2iwGc")
        mode_str = "Roboflow API"

    no_lane = args.no_lane
    if no_lane:
        lane_engine = None
        mode_str += " (no lane)"
    elif args.lane_model == "cv_magnet":
        from engine_cv_lane import CVLaneMagnetEngine
        lane_engine = CVLaneMagnetEngine(skip_frames=0)
        mode_str += " + CV-Magnet (0.4ms Native Ground-Snapper)"
    elif args.lane_model == "lstr":
        from engine_lstr import LSTR_Engine
        try:
            lane_engine = LSTR_Engine(variant="onnx", skip_frames=args.skip)
            mode_str += f" + LSTR-ONNX (180x320, skip{args.skip})"
        except Exception:
            lane_engine = LSTR_Engine(variant="culane", skip_frames=args.skip)
            mode_str += f" + LSTR-CULane (TorchScript, skip{args.skip})"
    else:
        lane_model = None
        if args.lane_fp16:
            lane_model = os.path.join(os.path.dirname(__file__), "models", "ufldv2_tusimple_res18_320x800_fp16.onnx")
        lane_engine = UFLDv2Engine(model_path=lane_model, skip_frames=args.skip)
        mode_str += f" + UFLD v2 {'fp16' if args.lane_fp16 else 'fp32'} skip{args.skip}"
    fusion = SpatialFusion(camera="front", focal_length=260)
    hud = VisualizerHUD()

    video_path = resolve_video_path(args.video)
    if not os.path.exists(video_path):
        print(f"[ERROR] Video not found: {video_path}")
        sys.exit(1)

    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 30
    print(f"Video: {os.path.basename(video_path)} | {total_frames} frames @ {src_fps:.1f} FPS")
    if no_lane:
        print(f"[INFO] Lane detection disabled (--no-lane). YOLO only mode.")

    if args.output:
        out_path = os.path.abspath(args.output)
        out_dir = os.path.dirname(out_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
    else:
        out_dir = os.path.join(os.path.dirname(__file__), "outputs")
        os.makedirs(out_dir, exist_ok=True)
        out_name = os.path.splitext(os.path.basename(video_path))[0] + "_result.mp4"
        out_path = os.path.join(out_dir, out_name)

    has_display = not args.no_display and os.name == "nt"
    out_writer = None

    frame_count = 0
    times = []
    total_dets = 0
    total_threats = 0
    t_start_all = time.time()

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        frame_count += 1
        if args.max_frames and frame_count > args.max_frames:
            break

        if args.scale != 1.0:
            frame = cv2.resize(frame, None, fx=args.scale, fy=args.scale)

        t0 = time.time()
        h, w = frame.shape[:2]

        if use_yolo26:
            detections = detector.infer(frame)
        else:
            temp_img_path = os.path.join(out_dir, "temp_frame.jpg")
            cv2.imwrite(temp_img_path, frame)
            detections = detector.infer(temp_img_path)

        lanes = {} if no_lane else lane_engine.infer(frame)
        results = fusion.process(detections, lanes, (h, w))
        output_frame = hud.draw(frame.copy(), results, lanes)
        t1 = time.time()
        times.append(t1 - t0)
        total_dets += len(detections)
        total_threats += sum(1 for r in results if r['is_threat'])

        if out_writer is None:
            out_fps = src_fps
            out_writer = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*"mp4v"), out_fps, (output_frame.shape[1], output_frame.shape[0]))
        out_writer.write(output_frame)

        if has_display:
            cv2.imshow("V.I.S.O.R.", output_frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        if frame_count % 30 == 0:
            avg_ms = 1000 * np.mean(times[-30:])
            elapsed = time.time() - t_start_all
            remaining = min(total_frames, args.max_frames or total_frames) - frame_count
            eta = (elapsed / frame_count) * remaining
            print(f"[{frame_count}/{min(total_frames, args.max_frames or total_frames)}] "
                  f"{avg_ms:.0f}ms/frame | {total_dets} dets | {total_threats} threats | ETA {eta/60:.1f}min")

    cap.release()
    if out_writer:
        out_writer.release()
    if has_display:
        cv2.destroyAllWindows()

    total_t = time.time() - t_start_all
    processed = min(total_frames, frame_count)
    print(f"\n{'='*50}")
    print(f"Done: {out_path}")
    print(f"Processed {frame_count}/{processed} frames in {total_t/60:.1f}min")
    print(f"Avg: {1000*np.mean(times):.0f}ms ({1/np.mean(times):.1f} FPS)")
    print(f"Total detections: {total_dets} | Threats: {total_threats}")

if __name__ == "__main__":
    main()
