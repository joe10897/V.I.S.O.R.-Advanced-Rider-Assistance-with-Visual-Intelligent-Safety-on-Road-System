# fusion.py
import math
from . import utils
from collections import deque

KNOWN_WIDTHS = {
    "car": 1.8,         # meters
    "motorcycle": 0.8,  # meters
    "person": 0.5,      # meters (average shoulder width)
    "bicycle": 0.6,     # meters
    "bus": 2.5,         # meters
    "truck": 2.5,       # meters
    "train": 3.0,       # meters (tram/light rail)
}

# --- Constants for Looming Detection ---
LOOMING_FRAME_COUNT = 8
LOOMING_AREA_INCREASE_RATIO = 1.3
REAR_THREAT_CONF_THRESHOLD = 0.25

# --- Constants for Lane Detection ---
LANE_X_RATIO_MIN = 0.25
LANE_X_RATIO_MAX = 0.75

class Fusion:
    def __init__(self, frame_width, frame_height, config=None):
        self.w = frame_width
        self.h = frame_height
        
        # Load params from config or defaults
        thresholds = config.get('thresholds', {}) if config else {}
        vision = config.get('vision', {}) if config else {}
        
        self.focal_length = vision.get('focal_length', 800)
        self.danger_dist = thresholds.get('danger_dist', 2.5)
        self.warning_dist = thresholds.get('warning_dist', 5.0)
        self.tilt_alert_threshold = thresholds.get('tilt_alert', 18.0)
        self.rear_threat_cy_threshold = thresholds.get('rear_threat_cy', 0.4)

    def estimate_distance(self, bbox, class_name):
        """
        Estimates the distance to an object based on its bounding box width.
        """
        if class_name not in KNOWN_WIDTHS:
            return float('inf')

        known_width = KNOWN_WIDTHS[class_name]
        pixel_width = bbox[2] - bbox[0]
        
        if pixel_width <= 0:
            return float('inf')

        return (known_width * self.focal_length) / pixel_width

    def detect_looming(self, bbox_history: deque):
        if len(bbox_history) < LOOMING_FRAME_COUNT:
            return False
            
        current_bbox = bbox_history[-1]
        past_bbox = bbox_history[-LOOMING_FRAME_COUNT]
        
        current_area = utils.bbox_area(current_bbox)
        past_area = utils.bbox_area(past_bbox)
        
        if past_area > 0 and current_area > (past_area * LOOMING_AREA_INCREASE_RATIO):
            return True
        return False

    def is_in_lane(self, det):
        cx, _ = utils.bbox_to_centroid(det.bbox)
        if (self.w * LANE_X_RATIO_MIN) < cx < (self.w * LANE_X_RATIO_MAX):
            return True
        return False

    def get_side_position(self, det):
        """
        判斷物件在畫面中的水平位置。
        返回 'left', 'center', 或 'right'。
        """
        cx, _ = utils.bbox_to_centroid(det.bbox)
        if cx < (self.w * LANE_X_RATIO_MIN):
            return 'left'
        elif cx > (self.w * LANE_X_RATIO_MAX):
            return 'right'
        else:
            return 'center'
        
    def classify_threat(self, det, class_name, bbox_history):
        """
        Classifies the threat level of a detected object.
        """
        cx, cy = utils.bbox_to_centroid(det.bbox)
        dist = self.estimate_distance(det.bbox, class_name)
        
        # 基本信心度門檻
        if det.confidence < REAR_THREAT_CONF_THRESHOLD:
            return None, dist

        # 距離太遠不處理
        if dist > self.warning_dist:
            return None, dist

        is_looming = self.detect_looming(bbox_history)
        in_lane = self.is_in_lane(det)
        
        # 正前方/正後方車道內的物件
        if in_lane and dist < self.danger_dist:
            return 'DANGEROUSLY_CLOSE', dist
            
        if in_lane and dist < self.warning_dist:
            return 'IN_LANE_APPROACHING', dist

        # 側邊物件（左右）：必須是靠近中 (looming) 或極近才會觸發，避免路邊停車誤報
        if not in_lane and dist < self.warning_dist:
            if is_looming:
                if dist < self.danger_dist:
                    return 'DANGEROUSLY_CLOSE', dist
                return 'SIDE_APPROACHING', dist
            elif dist < 1.5: # 極度靠近的側邊死角物件
                return 'DANGEROUSLY_CLOSE', dist
        
        return None, dist

    def is_tilt_alert(self, sensor_data):
        if abs(sensor_data.get('tilt_deg', 0.0)) > self.tilt_alert_threshold:
            return True
        return False
