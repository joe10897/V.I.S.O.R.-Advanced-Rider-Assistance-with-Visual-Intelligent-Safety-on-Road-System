import cv2
import numpy as np

class VisualizerHUD:
    def __init__(self):
        self.font = cv2.FONT_HERSHEY_SIMPLEX
        self.colors = {
            "safe": (0, 255, 0),
            "caution": (0, 255, 255),       # yellow
            "warning": (0, 165, 255),        # orange
            "critical": (0, 0, 255),         # red
            "danger": (0, 0, 255),
            "hud_blue": (238, 211, 34)
        }

    def draw(self, frame, fusion_results, lanes):
        h, w = frame.shape[:2]
        overlay = frame.copy()
        
        # 1. 繪製科技藍色自車道半透明路徑毯 (Ego-Lane Carpet)
        if 'left' in lanes and 'right' in lanes:
            pts_l = np.array(lanes['left'], np.int32) if len(lanes['left']) > 0 else None
            pts_r = np.array(lanes['right'], np.int32) if len(lanes['right']) > 0 else None
            
            if pts_l is not None and pts_r is not None and len(pts_l) > 2 and len(pts_r) > 2:
                lane_poly = np.vstack([pts_l, pts_r[::-1]])
                # 科技藍色填充 (BGR: 235, 145, 15)
                cv2.fillPoly(overlay, [lane_poly], (235, 145, 15))
                # 25% 透明度混合
                cv2.addWeighted(overlay, 0.25, frame, 0.75, 0, frame)

                # 邊界半透明細光暈線 (Subtle edge glow)
                cv2.polylines(frame, [pts_l], False, (200, 255, 100), 1, cv2.LINE_AA)
                cv2.polylines(frame, [pts_r], False, (200, 255, 100), 1, cv2.LINE_AA)

        # 2. 繪製彩色圓點車道線 (Dotted Lines, Anti-Aliased)
        if 'left' in lanes:
            for pt in lanes['left']:
                cv2.circle(frame, tuple(pt), 3, (120, 255, 50), -1, cv2.LINE_AA)  # 左側：電光綠圓點
                
        if 'right' in lanes:
            for pt in lanes['right']:
                cv2.circle(frame, tuple(pt), 3, (120, 255, 50), -1, cv2.LINE_AA)  # 右側：電光綠圓點 (一致的高科技 HUD 視覺)

        # 2. 繪製偵測目標 (TTC-based threat coloring)
        for res in fusion_results:
            bbox = [int(b) for b in res['bbox']]
            dist = res['distance']
            threat_level = res.get('threat_level', 'safe')
            ttc = res['ttc']

            if (bbox[2] - bbox[0]) < 30:
                continue

            color = self.colors.get(threat_level, self.colors['hud_blue'])
            is_threat = threat_level in ("critical", "warning") and ttc < 3.0

            if is_threat:
                color = self.colors.get(threat_level, self.colors['warning'])
                self._draw_detailed_panel(frame, res, color)
            elif res.get('lane_status') == "IN_LANE" and dist < 35.0:
                # 本車道常態跟車 (等紅燈或同速巡航)：使用科技綠簡約標籤顯示車距，絕不標黃色！
                self._draw_compact_tag(frame, bbox, dist, (0, 220, 100), res['class'])
            else:
                # 路邊臨停、對向車、鄰車道車輛：使用極簡微灰角標，不遮擋視野，不亮警示黃色
                self._draw_corner_brackets(frame, bbox, (150, 150, 150))

        return frame

    def _draw_corner_brackets(self, frame, bbox, color):
        x1, y1, x2, y2 = bbox
        length = 15
        thickness = 1
        # Top-left
        cv2.line(frame, (x1, y1), (x1+length, y1), color, thickness)
        cv2.line(frame, (x1, y1), (x1, y1+length), color, thickness)
        # Top-right
        cv2.line(frame, (x2, y1), (x2-length, y1), color, thickness)
        cv2.line(frame, (x2, y1), (x2, y1+length), color, thickness)
        # Bottom-left
        cv2.line(frame, (x1, y2), (x1+length, y2), color, thickness)
        cv2.line(frame, (x1, y2), (x1, y2-length), color, thickness)
        # Bottom-right
        cv2.line(frame, (x2, y2), (x2-length, y2), color, thickness)
        cv2.line(frame, (x2, y2), (x2, y2-length), color, thickness)

    def _draw_compact_tag(self, frame, bbox, dist, color, class_name):
        x1, y1, x2, y2 = bbox
        label_text = f"{class_name.upper()}:{dist}m"
        (tw, th), _ = cv2.getTextSize(label_text, self.font, 0.35, 1)
        # Background box for the text
        cv2.rectangle(frame, (x1, y1-th-10), (x1+tw+10, y1), color, -1)
        cv2.putText(frame, label_text, (x1+5, y1-5), self.font, 0.35, (0,0,0), 1)
        self._draw_corner_brackets(frame, bbox, color)

    def _draw_detailed_panel(self, frame, res, color):
        bbox = res['bbox']
        x2, y1 = int(bbox[2]), int(bbox[1])
        px, py = x2 + 20, y1 - 30
        
        # 繪製半透明數據條
        cv2.line(frame, (int(bbox[0]), y1), (px, py), color, 1)
        
        level_tag = res.get('threat_level', '?').upper()
        panel_text = f"[{level_tag}] {res['class'].upper()} {res['distance']}m | TTC {res['ttc']}s"
        (tw, th), _ = cv2.getTextSize(panel_text, self.font, 0.45, 1)
        
        # 背景
        cv2.rectangle(frame, (px, py-th-10), (px+tw+20, py+10), (0,0,0), -1)
        cv2.rectangle(frame, (px, py-th-10), (px+tw+20, py+10), color, 1)
        # 文字
        cv2.putText(frame, panel_text, (px+10, py), self.font, 0.45, (255,255,255), 1)
        # BBox 強化
        cv2.rectangle(frame, (int(bbox[0]), int(bbox[1])), (int(bbox[2]), int(bbox[3])), color, 2)
