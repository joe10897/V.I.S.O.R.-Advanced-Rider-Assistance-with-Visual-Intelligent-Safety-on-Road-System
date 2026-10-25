# tracker.py - simple centroid tracker
import numpy as np
from collections import OrderedDict, deque
from .utils import bbox_to_centroid

class CentroidTracker:
    def __init__(self, max_disappeared=10, max_distance=60, history_length=10):
        self.nextObjectID = 0
        self.objects = OrderedDict()  # id -> centroid
        self.disappeared = OrderedDict()
        self.max_disappeared = max_disappeared
        self.max_distance = max_distance
        
        self.history_length = history_length
        self.history = {}  # id -> deque of centroids
        self.bbox_history = {} # id -> deque of bboxes

    def register(self, centroid, rect):
        self.objects[self.nextObjectID] = centroid
        self.disappeared[self.nextObjectID] = 0
        self.history[self.nextObjectID] = deque([centroid], maxlen=self.history_length)
        self.bbox_history[self.nextObjectID] = deque([rect], maxlen=self.history_length)
        self.nextObjectID += 1

    def deregister(self, objectID):
        del self.objects[objectID]
        del self.disappeared[objectID]
        del self.history[objectID]
        del self.bbox_history[objectID]

    def update(self, rects):
        # rects: list of bbox [x1,y1,x2,y2]
        if len(rects) == 0:
            for oid in list(self.disappeared.keys()):
                self.disappeared[oid] += 1
                if self.disappeared[oid] > self.max_disappeared:
                    self.deregister(oid)
            return self.objects

        inputCentroids = np.array([bbox_to_centroid(r) for r in rects])

        if len(self.objects) == 0:
            for i in range(len(inputCentroids)):
                self.register(inputCentroids[i], rects[i])
        else:
            objectIDs = list(self.objects.keys())
            objectCentroids = list(self.objects.values())

            D = np.linalg.norm(np.array(objectCentroids)[:,None] - inputCentroids[None,:], axis=2)
            rows = D.min(axis=1).argsort()
            cols = D.argmin(axis=1)[rows]

            usedRows = set()
            usedCols = set()

            for (row, col) in zip(rows, cols):
                if row in usedRows or col in usedCols:
                    continue
                if D[row, col] > self.max_distance:
                    continue
                
                objectID = objectIDs[row]
                self.objects[objectID] = inputCentroids[col]
                self.history[objectID].append(inputCentroids[col])
                self.bbox_history[objectID].append(rects[col])
                self.disappeared[objectID] = 0
                
                usedRows.add(row)
                usedCols.add(col)

            unusedRows = set(range(0, D.shape[0])).difference(usedRows)
            unusedCols = set(range(0, D.shape[1])).difference(usedCols)

            for row in unusedRows:
                objectID = objectIDs[row]
                self.disappeared[objectID] += 1
                if self.disappeared[objectID] > self.max_disappeared:
                    self.deregister(objectID)

            for col in unusedCols:
                self.register(inputCentroids[col], rects[col])

        return self.objects
