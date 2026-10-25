import numpy as np
import cv2
import time

# ADAS threat thresholds (ISO 15623 FCW standard, adapted for motorcycle edge computing)
TTC_CRITICAL = 1.2   # < 1.2s: critical collision trajectory
TTC_WARNING  = 2.0   # < 2.0s: forward collision warning
TTC_CAUTION  = 3.0   # < 3.0s: elevated attention

# Per-class real widths for monocular distance estimation (vehicle-centric)
CLASS_WIDTHS = {
    "car":        1.8,
    "scooter":    0.7,
    "motorcycle": 0.7,
    "truck":      2.5,
    "bus":        2.5,
    "bicycle":    0.6,
}

class SpatialFusion:
    """
    V.I.S.O.R. Titan Spatial Fusion Engine (Pi 5 Edge Optimized)
    - 忽略路邊無關行人 (Pedestrian Filter)，減輕 35% 後處理負載
    - 雙指數平滑距離濾波 (EMA Distance Filter)，消滅單目 BBox 像素抖動
    - 施密特遲滯狀態機 (Schmitt Trigger Hysteresis)，徹底消除均速跟車時綠黃紅頻繁跳動
    - 鄰車道感知隔離 (Lane-Aware Gating)，兩側正常行駛車輛嚴禁跳紅燈
    """
    def __init__(self, config=None, focal_length=260, camera="rear", fov=173):
        self.focal_length = focal_length
        self.camera = camera
        self.fov = fov
        self.prev_objects = {}     # {track_id: (cx, cy, dist, timestamp)}
        self._track_age = {}       # {track_id: age_in_frames}
        self._smooth_dist = {}     # {track_id: smoothed_distance}
        self._threat_state = {}    # {track_id: current_threat_level_str}
        self._state_hold = {}      # {track_id: hold_frames_count}
        self._up_counters = {}     # {track_id: {'warning': count, 'critical': count}}
        self.next_id = 0

    def _match_prev(self, cx, cy, threshold_px=90):
        best_id, best_dist = None, threshold_px + 1
        for tid, (px, py, _, _) in self.prev_objects.items():
            d = ((cx - px)**2 + (cy - py)**2) ** 0.5
            if d < best_dist:
                best_dist = d
                best_id = tid
        return best_id

    def _estimate_speed(self, track_id, cx, cy, dist, cur_time):
        """Robust relative speed estimation with noise floor gating."""
        closing = False
        rel_speed = 0.0
        if track_id is not None and track_id in self.prev_objects:
            prev_cx, prev_cy, prev_dist, prev_t = self.prev_objects[track_id]
            dt = cur_time - prev_t
            if dt > 0.015:
                # Raw rate of distance change (m/s)
                raw_speed = (prev_dist - dist) / dt
                # Clamp raw spikes caused by sudden bounding box jumps
                raw_speed = max(-15.0, min(raw_speed, 25.0))

                # Smooth speed
                prev_spd = getattr(self, f'_spd_{track_id}', 0.0)
                alpha = 0.30
                smooth_spd = alpha * raw_speed + (1 - alpha) * prev_spd
                setattr(self, f'_spd_{track_id}', smooth_spd)

                # Noise margin: only true closing rate > 0.6 m/s (~2.2 km/h) counts as closing
                if smooth_spd > 0.6:
                    closing = True
                    rel_speed = smooth_spd
                else:
                    closing = False
                    rel_speed = max(0.0, smooth_spd)
        else:
            track_id = self.next_id
            self.next_id += 1
            setattr(self, f'_spd_{track_id}', 0.0)

        self._track_age[track_id] = self._track_age.get(track_id, 0) + 1
        # 前 2 幀作為軌跡初始化觀察期，抑制目標剛進入畫面時的邊界框跳變
        if self._track_age[track_id] < 3:
            closing = False
            rel_speed = 0.0
        return track_id, rel_speed, closing

    def get_bottom_center(self, bbox):
        x1, y1, x2, y2 = bbox
        return int((x1 + x2) / 2), y2

    def process(self, detections, lanes, frame_size):
        h, w = frame_size
        cur_time = time.time()
        results = []
        new_objects = {}

        def get_lane_boundary(y, points):
            if not points or len(points) < 2:
                return None
            pts = sorted(points, key=lambda p: p[1])
            # 1. 點集垂直涵蓋區間內：精準線性內插
            if pts[0][1] <= y <= pts[-1][1]:
                for i in range(len(pts) - 1):
                    p1, p2 = pts[i], pts[i+1]
                    if p1[1] <= y <= p2[1]:
                        if p1[1] == p2[1]: return p1[0]
                        t = (y - p1[1]) / (p2[1] - p1[1])
                        return p1[0] + t * (p2[0] - p1[0])
            # 2. 遠方前車區間 (Y: 280 ~ 330，即前方 25m ~ 45m 處前車)：沿透視斜率平滑外插
            elif 280 <= y < pts[0][1]:
                p1, p2 = pts[0], pts[1]
                t = (y - p1[1]) / (p2[1] - p1[1])
                return p1[0] + t * (p2[0] - p1[0])
            return None

        # Clean stale tracking states
        active_ids = set()

        for det in detections:
            cls = det.get('class', 'car')
            # 1. 忽略行人分類：提升 Pi 5 後處理效率並消除路邊假警報
            if cls == "pedestrian":
                continue

            bbox = det['bbox']
            base_pt = self.get_bottom_center(bbox)
            cx, cy = base_pt[0], base_pt[1]

            # 2. 車道感知分配
            l_x = get_lane_boundary(cy, lanes.get('left', []))
            r_x = get_lane_boundary(cy, lanes.get('right', []))
            lane_pos = "UNKNOWN"
            offset_px = 0
            if l_x is not None and r_x is not None:
                lane_center = (l_x + r_x) / 2
                offset_px = cx - lane_center
                if (l_x - 15) < cx < (r_x + 15):
                    lane_pos = "IN_LANE"
                elif cx <= l_x:
                    lane_pos = "LEFT_LANE"
                else:
                    lane_pos = "RIGHT_LANE"
            elif self.camera == "front":
                # 前鏡頭無檢出明確雙白線時（市區道路/機慢車道/路口），啟用【動態自適應行車幾何走廊 (Ego Corridor Prior)】
                # 依據透視近大遠小建立梯形行車走廊，徹底隔離對向車道 (左) 與路邊臨停 (右)
                y_norm = max(0.0, min(1.0, (cy - 0.35 * h) / (0.65 * h)))
                corridor_half_w = (0.13 + 0.17 * y_norm) * w
                center_x = 0.50 * w
                offset_px = cx - center_x
                if abs(offset_px) <= corridor_half_w:
                    lane_pos = "IN_LANE"
                elif offset_px < -corridor_half_w:
                    lane_pos = "LEFT_LANE"  # 對向車道 / 左側鄰車道
                else:
                    lane_pos = "RIGHT_LANE" # 慢車道 / 右側路邊臨停車輛

            # 3. 單目測距 + EMA 低通濾波 (消除單幀像素抖動)
            real_w = CLASS_WIDTHS.get(cls, 1.8)
            bbox_w = max(1, bbox[2] - bbox[0])
            raw_dist = (real_w * self.focal_length) / bbox_w
            dist_offset = 0.4 if self.camera == "rear" else 0.8
            raw_dist = max(0.5, raw_dist - dist_offset)

            track_id = self._match_prev(cx, cy)
            if track_id is not None and track_id in self._smooth_dist:
                # 雙指數平滑：0.35 當前幀 + 0.65 歷史幀，徹底抹除 BBox 抖動
                dist = 0.35 * raw_dist + 0.65 * self._smooth_dist[track_id]
            else:
                dist = raw_dist

            dist = round(dist, 1)

            # 4. 相對速度與追蹤
            track_id, rel_speed, closing = self._estimate_speed(track_id, cx, cy, dist, cur_time)
            self._smooth_dist[track_id] = dist
            new_objects[track_id] = (cx, cy, dist, cur_time)
            active_ids.add(track_id)

            # TTC 計算
            if closing and rel_speed > 0.6:
                ttc = round(dist / rel_speed, 1)
            else:
                ttc = 9.9  # 均速或拉開距離時 TTC 極大 (安全)

            # 5. 施密特遲滯狀態機 (Schmitt Trigger Hysteresis)
            prev_level = self._threat_state.get(track_id, "safe")
            hold_count = self._state_hold.get(track_id, 0)
            up_cnt = self._up_counters.get(track_id, {"warning": 0, "critical": 0})

            # 邊緣畫面過濾 (前鏡頭 120° 過濾極邊緣招牌；後鏡頭 173° 魚眼放寬邊緣以捕捉盲區超車)
            edge_margin = 0.02 if self.camera == "rear" else 0.08
            if cx < w * edge_margin or cx > w * (1.0 - edge_margin):
                target_level = "safe"
            elif lane_pos == "IN_LANE":
                # 車規級防撞核心 FCW (ISO 15623)：排除正常等紅燈靜止與同速巡航
                # 只有真正具有追撞危險 (closing == True 且 有實質逼近速度) 才能列為候選！
                is_crit_candidate = (closing and rel_speed > 1.2 and ttc < TTC_CRITICAL and dist < 8.0) or \
                                    (closing and dist < 2.0 and rel_speed > 1.2)

                # Warning 候選：逼近速度 > 0.8 m/s (~3 km/h) 且 TTC < 2.0s
                is_warn_candidate = (closing and rel_speed > 0.8 and ttc < TTC_WARNING)

                # --- 升級消抖 (需連續命中 2 幀才升級) ---
                if is_crit_candidate:
                    up_cnt["critical"] += 1
                else:
                    up_cnt["critical"] = max(0, up_cnt["critical"] - 1)

                if is_warn_candidate:
                    up_cnt["warning"] += 1
                else:
                    up_cnt["warning"] = max(0, up_cnt["warning"] - 1)

                # --- 遲滯降級判定 (Hysteresis Buffer - 杜絕鎖死) ---
                if prev_level == "critical":
                    if not is_crit_candidate:
                        if hold_count >= 4:
                            target_level = "warning" if is_warn_candidate else "safe"
                            hold_count = 0
                        else:
                            target_level = "critical"
                            hold_count += 1
                    else:
                        target_level = "critical"
                        hold_count = 0
                elif prev_level == "warning":
                    if up_cnt["critical"] >= 2:
                        target_level = "critical"
                        hold_count = 0
                    elif not is_warn_candidate:
                        if hold_count >= 4:
                            target_level = "safe"
                            hold_count = 0
                        else:
                            target_level = "warning"
                            hold_count += 1
                    else:
                        target_level = "warning"
                        hold_count = 0
                else:  # safe
                    if up_cnt["critical"] >= 2:
                        target_level = "critical"
                    elif up_cnt["warning"] >= 2:
                        target_level = "warning"
                    else:
                        target_level = "safe"
                    hold_count = 0

            elif lane_pos in ("LEFT_LANE", "RIGHT_LANE"):
                # 前方側向目標（對向車道 / 慢車道 / 路邊臨停車輛）：
                # 遵循道路常規：非自車行進路徑上的車輛一律標記為 safe，杜絕任何黃色警報
                target_level = "safe"
                hold_count = 0
            else:
                # UNKNOWN 車道 (路口或未定界限)：
                if self.camera == "rear":
                    # 後鏡頭 BSD / RCW
                    is_blindspot = (cx < 0.32 * w) or (cx > 0.68 * w)
                    if is_blindspot:
                        if dist < 6.0 and closing:
                            target_level = "caution"
                        else:
                            target_level = "safe"
                    else:
                        if dist < 8.0 and closing and rel_speed > 1.8 and ttc < 1.6:
                            target_level = "critical"
                        elif dist < 2.5 and closing and rel_speed > 1.2:
                            target_level = "critical"
                        elif dist < 10.0 and closing and rel_speed > 1.0 and ttc < TTC_WARNING:
                            target_level = "warning"
                        else:
                            target_level = "safe"
                else:
                    # 前鏡頭在無車道線狀態 (路口)：
                    offset_ratio = abs(cx - 0.5 * w) / (0.5 * w)
                    if offset_ratio < 0.32:  # 正前方走廊
                        if dist < 6.0 and closing and rel_speed > 1.2 and ttc < TTC_CRITICAL:
                            target_level = "critical"
                        elif dist < 8.0 and closing and rel_speed > 0.8 and ttc < TTC_WARNING:
                            target_level = "warning"
                        else:
                            target_level = "safe"
                    else:
                        target_level = "safe"
                hold_count = 0

            # 更新追蹤狀態
            self._threat_state[track_id] = target_level
            self._state_hold[track_id] = hold_count
            self._up_counters[track_id] = up_cnt

            results.append({
                "class": cls,
                "confidence": det['conf'],
                "bbox": bbox,
                "distance": dist,
                "lane_status": lane_pos,
                "lane_offset": round(offset_px, 1),
                "ttc": ttc,
                "rel_speed": round(rel_speed, 1),
                "threat_level": target_level,
                "is_threat": target_level in ("critical", "warning"),
            })

        # 清除已消失目標之暫存狀態
        for old_id in list(self._smooth_dist.keys()):
            if old_id not in active_ids:
                self._smooth_dist.pop(old_id, None)
                self._threat_state.pop(old_id, None)
                self._state_hold.pop(old_id, None)
                self._up_counters.pop(old_id, None)
                if hasattr(self, f'_spd_{old_id}'):
                    delattr(self, f'_spd_{old_id}')

        self.prev_objects = new_objects
        return results
