"""ByteTrack identity association shared by YOLO and ONNX pose backends."""
from types import SimpleNamespace
import numpy as np


class PlayerIdentityTracker:
    def __init__(self, inference_fps=10):
        from ultralytics.trackers.byte_tracker import BYTETracker
        self.tracker = BYTETracker(SimpleNamespace(
            track_high_thresh=.20, track_low_thresh=.1, new_track_thresh=.20,
            track_buffer=max(10, round(inference_fps*2)), match_thresh=.85, fuse_score=True))

    def update(self, detections, shape):
        from ultralytics.engine.results import Boxes
        data = np.array([[*item.box, item.confidence, 0] for item in detections], dtype=np.float32).reshape(-1, 6)
        tracks = self.tracker.update(Boxes(data, shape[:2]))
        result = []
        for row in tracks:
            index = int(row[-1])
            if 0 <= index < len(detections):
                detection = detections[index]
                detection.track_id = int(row[4])
                result.append(detection)
        return result
