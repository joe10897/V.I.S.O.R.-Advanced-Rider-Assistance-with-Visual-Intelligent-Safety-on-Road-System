# vision/utils.py
import cv2

def bbox_to_centroid(bbox):
    x1,y1,x2,y2 = bbox
    cx = int((x1+x2)/2)
    cy = int((y1+y2)/2)
    return (cx, cy)

def bbox_area(bbox):
    x1,y1,x2,y2 = bbox
    return max(0, x2-x1) * max(0, y2-y1)

def draw_label(img, text, pos, bg=(0,0,0), fg=(255,255,255)):
    x,y = pos
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.5
    thickness = 1
    (w,h), _ = cv2.getTextSize(text, font, scale, thickness)
    cv2.rectangle(img, (x, y-h-6), (x+w, y+6), bg, -1)
    cv2.putText(img, text, (x, y), font, scale, fg, thickness, cv2.LINE_AA)
