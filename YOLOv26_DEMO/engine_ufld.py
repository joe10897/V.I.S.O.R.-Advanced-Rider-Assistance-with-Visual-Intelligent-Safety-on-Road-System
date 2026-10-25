import cv2
import numpy as np
import time
import os
import onnxruntime as ort

class UFLDv2Engine:
    def __init__(self, model_path=None, use_cuda=False, skip_frames=0):
        if model_path is None:
            model_path = os.path.join(os.path.dirname(__file__), "models", "ufldv2_tusimple_res18_320x800.onnx")
        self.model_path = model_path
        self.skip_frames = skip_frames
        self._cached_lanes = None
        self._skip_counter = 0

        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"] if use_cuda else ["CPUExecutionProvider"]
        self.session = ort.InferenceSession(model_path, providers=providers)
        inp = self.session.get_inputs()[0]
        self.input_name = inp.name
        self.input_dtype = inp.type  # e.g. "tensor(float)" or "tensor(float16)"
        self.use_fp16 = "float16" in self.input_dtype

        self.input_h = None
        self.input_w = None
        self.num_rows = None
        self.num_grids_row = None
        self.num_grids_col = None
        self._detect_config(inp)

    def _detect_config(self, inp):
        shape = inp.shape
        self.input_h = shape[2] if shape[2] and isinstance(shape[2], int) else 288
        self.input_w = shape[3] if shape[3] and isinstance(shape[3], int) else 800

        num_outs = len(self.session.get_outputs())
        if num_outs >= 4:
            self.is_v2 = True
            out0_shape = self.session.get_outputs()[0].shape
            self.num_grids_row = out0_shape[1] if out0_shape[1] else 100
            self.num_rows = out0_shape[2] if out0_shape[2] else 56
            self.num_grids_col = self.session.get_outputs()[1].shape[1] if self.session.get_outputs()[1].shape else 100
        else:
            self.is_v2 = False
            out_shape = self.session.get_outputs()[0].shape
            self.num_grids_row = out_shape[1] if out_shape[1] else 201
            self.num_rows = out_shape[2] if out_shape[2] else 18
        self.num_lanes = 4
        self.row_anchor = np.linspace(0, 1, self.num_rows)

        # Lane indices: 0=leftmost, 1=left, 2=right, 3=rightmost
        self.left_lane_idx = 1
        self.right_lane_idx = 2

        self.smooth_lx = None
        self.smooth_rx = None
        self.last_h = None
        self.last_w = None
        self.num_points = 25
        self.y_eval_norm = np.linspace(0.48, 0.96, self.num_points)

        mode_str = f"v2 {'fp16' if self.use_fp16 else 'fp32'} {self.input_h}x{self.input_w}"
        print(f"UFLD {mode_str} ONNX ready: {os.path.basename(self.model_path)}")

    def preprocess(self, frame):
        img = cv2.resize(frame, (self.input_w, self.input_h))
        dtype = np.float16 if self.use_fp16 else np.float32
        img = img.astype(dtype) / 255.0
        mean = np.array([0.485, 0.456, 0.406], dtype=dtype).reshape(1, 1, 3)
        std = np.array([0.229, 0.224, 0.225], dtype=dtype).reshape(1, 1, 3)
        img = (img - mean) / std
        img = img.transpose(2, 0, 1)
        return np.expand_dims(img, axis=0)

    def _fit_lane(self, pts, y_eval, w, min_y, max_y):
        valid = [p for p in pts if min_y <= p[1] <= max_y]
        if len(valid) < 5:
            return None
        xs = np.array([p[0] for p in valid], dtype=float)
        ys = np.array([p[1] for p in valid], dtype=float)
        try:
            poly = np.polyfit(ys, xs, 2)
            fit_xs = np.polyval(poly, y_eval)
            if np.any(fit_xs < -50) or np.any(fit_xs > w + 50):
                return None
            return fit_xs
        except Exception:
            return None

    def infer(self, frame):
        self._skip_counter += 1
        h, w = frame.shape[:2]
        y_grid = (self.y_eval_norm * h).astype(int)

        # Perspective ego corridor prior
        yn = np.clip((self.y_eval_norm - 0.48) / 0.48, 0.0, 1.0)
        corridor_hw = (0.08 + 0.15 * yn) * w
        corridor_w = 2.0 * corridor_hw
        prior_lx = 0.50 * w - corridor_hw
        prior_rx = 0.50 * w + corridor_hw

        if self.smooth_lx is None or self.last_h != h or self.last_w != w:
            self.smooth_lx = prior_lx.copy()
            self.smooth_rx = prior_rx.copy()
            self.last_h = h
            self.last_w = w

        # Skip-frame logic: if skipped, smoothly glide with last known state
        need_infer = True
        if self.skip_frames and self._cached_lanes is not None:
            if self._skip_counter % (self.skip_frames + 1) != 0:
                need_infer = False

        if need_infer:
            input_tensor = self.preprocess(frame)
            outputs = self.session.run(None, {self.input_name: input_tensor})

            if self.is_v2:
                loc_row = outputs[0][0].astype(np.float32)
                exist_row = outputs[2][0].astype(np.float32)
                exist_logits = exist_row[1]
            else:
                loc_row = outputs[0][0].astype(np.float32)
                exist_row = loc_row[:, :, :]

            exist_probs = 1.0 / (1.0 + np.exp(-exist_logits))
            loc_row_max = loc_row.max(axis=0, keepdims=True)
            loc_row_exp = np.exp(loc_row - loc_row_max)
            loc_probs = loc_row_exp / loc_row_exp.sum(axis=0, keepdims=True)
            grid_indices = np.arange(self.num_grids_row, dtype=np.float32).reshape(-1, 1, 1)
            loc_cols = (loc_probs * grid_indices).sum(axis=0)

            left_pts = []
            right_pts = []

            for row_i in range(self.num_rows):
                py = int(self.row_anchor[row_i] * h)
                if py < int(0.45 * h):  # 忽略地平線以上碎片
                    continue
                if exist_probs[row_i, self.left_lane_idx] > 0.35:
                    col = loc_cols[row_i, self.left_lane_idx]
                    px = int(col / self.num_grids_row * w)
                    left_pts.append((px, py))
                if exist_probs[row_i, self.right_lane_idx] > 0.35:
                    col = loc_cols[row_i, self.right_lane_idx]
                    px = int(col / self.num_grids_row * w)
                    right_pts.append((px, py))

            # 擬合二階平滑曲線
            l_xs = self._fit_lane(left_pts, y_grid, w, min_y=int(0.48 * h), max_y=int(0.98 * h))
            r_xs = self._fit_lane(right_pts, y_grid, w, min_y=int(0.48 * h), max_y=int(0.98 * h))

            # 斜率合法性檢查 (左線向左下傾斜，右線向右下傾斜)
            cand_l = l_xs if (l_xs is not None and l_xs[0] > l_xs[-1] and 0 < l_xs[-1] < 0.48 * w) else None
            cand_r = r_xs if (r_xs is not None and r_xs[-1] > r_xs[0] and 0.52 * w < r_xs[-1] < w) else None

            # 智慧融合與平行投影補全
            if cand_l is not None and cand_r is not None:
                target_lx = cand_l
                target_rx = cand_r
            elif cand_l is not None:
                target_lx = cand_l
                target_rx = np.clip(cand_l + corridor_w, 0, w)
            elif cand_r is not None:
                target_rx = cand_r
                target_lx = np.clip(cand_r - corridor_w, 0, w)
            else:
                target_lx = prior_lx
                target_rx = prior_rx

            # 點空間低通平滑與迴轉率限幅 (單幀位移 <= 14px)
            alpha = 0.30
            step_l = np.clip(alpha * (target_lx - self.smooth_lx), -14.0, 14.0)
            step_r = np.clip(alpha * (target_rx - self.smooth_rx), -14.0, 14.0)
            self.smooth_lx += step_l
            self.smooth_rx += step_r

        result = {
            'left': [[int(x), int(y)] for x, y in zip(self.smooth_lx, y_grid)],
            'right': [[int(x), int(y)] for x, y in zip(self.smooth_rx, y_grid)]
        }
        self._cached_lanes = result
        return result

if __name__ == "__main__":
    engine = UFLDv2Engine()
    test_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    lanes = engine.infer(test_frame)
    print(f"Detected lanes L:{len(lanes['left'])} R:{len(lanes['right'])}")
