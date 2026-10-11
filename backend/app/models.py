"""Explicit local-only adapters for the reference model families."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from .runtime import select_device
from .config import WEIGHTS

FILES = {
    'tennis': 'tennis-ball.pt', 'badminton': 'yolo11s-ball.pt',
    'yolo-small': 'yolo11s-pose.pt', 'yolo-nano': 'yolo11n-pose.pt',
    'yolox': 'yolox_nano_8xb8-300e_humanart-40f6f0d0.onnx',
    'rtmpose': 'rtmpose-s_simcc-body7_pt-body7_420e-256x192-acd4a1ef_20230504.onnx',
    'rtmo': 'rtmo-s_8xb32-600e_body7-640x640-dac2bf74_20231211.onnx',
}

def required(sport, pose):
    return [FILES[sport], FILES[pose]] + ([FILES['yolox']] if pose == 'rtmpose' else [])

def check_weights(sport, pose):
    missing = [name for name in required(sport, pose) if not (WEIGHTS / name).is_file()]
    if missing:
        raise FileNotFoundError('Missing exact reference weights: ' + ', '.join(missing))

def inventory():
    return [{'key': key, 'file': name, 'available': (WEIGHTS / name).is_file()} for key, name in FILES.items()]

@dataclass
class Detection:
    box: list[float]
    confidence: float
    keypoints: list = field(default_factory=list)
    track_id: int | None = None

    @property
    def center(self):
        x1, y1, x2, y2 = self.box
        return ((x1 + x2) / 2, (y1 + y2) / 2)

    @property
    def foot(self):
        return ((self.box[0] + self.box[2]) / 2, self.box[3])

class PoseAdapter(ABC):
    @abstractmethod
    def detect(self, frame) -> list[Detection]: ...

class YoloPoseAdapter(PoseAdapter):
    def __init__(self, path, device, image_size=640):
        from ultralytics import YOLO
        self.model, self.device = YOLO(str(path)), device
        self.image_size = image_size

    def detect(self, frame):
        result = self.model.predict(frame, device=self.device, imgsz=self.image_size, half=self.device != 'cpu', conf=0.15, verbose=False)[0]
        if result.boxes is None:
            return []
        boxes = result.boxes.xyxy.cpu().tolist()
        confidence = result.boxes.conf.cpu().tolist()
        points = result.keypoints.data.cpu().tolist() if result.keypoints is not None else [[] for _ in boxes]
        return [Detection(box, score, pose) for box, score, pose in zip(boxes, confidence, points)]

class OnnxPoseAdapter(PoseAdapter):
    def __init__(self, family, device):
        from rtmlib import RTMO, RTMPose, YOLOX
        backend = {'backend': 'onnxruntime', 'device': 'cuda' if device != 'cpu' else 'cpu'}
        self.family = family
        if family == 'rtmo':
            self.pose = RTMO(onnx_model=str(WEIGHTS / FILES[family]), model_input_size=(640, 640), **backend)
        else:
            self.detector = YOLOX(onnx_model=str(WEIGHTS / FILES['yolox']), model_input_size=(416, 416), **backend)
            self.pose = RTMPose(onnx_model=str(WEIGHTS / FILES[family]), model_input_size=(192, 256), **backend)
        for tool in [self.pose] + ([self.detector] if family == 'rtmpose' else []):
            if device != 'cpu' and 'CUDAExecutionProvider' not in tool.session.get_providers():
                raise RuntimeError('ONNX Runtime failed to initialize CUDA. CPU fallback has been refused.')

    def detect(self, frame):
        import numpy as np
        if self.family == 'rtmo':
            points, scores = self.pose(frame)
        else:
            boxes = self.detector(frame)
            if len(boxes) == 0:
                return []
            points, scores = self.pose(frame, bboxes=boxes)
        results = []
        for pose, confidence in zip(points, scores):
            visible = pose[confidence > 0.4]
            if len(visible) < 5:
                continue
            box = [*visible.min(axis=0).tolist(), *visible.max(axis=0).tolist()]
            results.append(Detection(box, float(np.mean(confidence)), np.column_stack((pose, confidence)).tolist()))
        return results

class ModelBundle:
    def __init__(self, sport, pose, device='cuda', image_size=640):
        check_weights(sport, pose)
        import torch
        from ultralytics import YOLO
        self.device = select_device(device, pose)
        self.image_size = image_size
        self.ball = YOLO(str(WEIGHTS / FILES[sport]))
        self.pose = YoloPoseAdapter(WEIGHTS / FILES[pose], self.device, max(image_size,960) if pose=='yolo-small' else image_size) if pose.startswith('yolo-') else OnnxPoseAdapter(pose, self.device)
        self.runtime = {'device': 'cuda:0' if self.device != 'cpu' else 'cpu',
                        'gpu': torch.cuda.get_device_name(0) if self.device != 'cpu' else None,
                        'half_precision': self.device != 'cpu', 'inference_size': image_size,
                        'pose_provider': 'CUDAExecutionProvider' if pose in ('rtmpose','rtmo') and self.device != 'cpu' else ('CPUExecutionProvider' if pose in ('rtmpose','rtmo') else 'PyTorch')}

    def infer(self, frame, court=None):
        result = self.ball.predict(frame, device=self.device, imgsz=self.image_size, half=self.device != 'cpu', conf=0.12, verbose=False)[0]
        objects = []
        height, width = frame.shape[:2]
        if result.boxes is not None:
            for box, score in zip(result.boxes.xyxy.cpu().tolist(), result.boxes.conf.cpu().tolist()):
                w, h = box[2] - box[0], box[3] - box[1]
                if w > 0 and h > 0 and w * h < width * height * 0.004 and max(w / h, h / w) < 4:
                    objects.append(Detection(box, score))
        from .player_detection import detect_players
        return objects, detect_players(self.pose,frame,court)
