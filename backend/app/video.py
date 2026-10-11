"""Bounded decoding and overlapping chunks with stable source timestamps."""
from dataclasses import dataclass
from queue import Queue, Full
from threading import Thread, Event
from collections import deque
import time
import cv2
import numpy as np

@dataclass
class Frame:
    index: int
    time: float
    image: np.ndarray

@dataclass
class Chunk:
    index: int
    frames: list[Frame]

class VideoSource:
    def __init__(self, source, live=False, chunk_seconds=10.0, overlap_seconds=1.0, max_width=960):
        self.source, self.live = source, live
        self.chunk_seconds, self.overlap_seconds, self.max_width = chunk_seconds, overlap_seconds, max_width
        self.stop = Event()
        self.queue = Queue(maxsize=1)
        self.fps, self.total_frames = 30.0, 0

    def _put(self, value):
        while not self.stop.is_set():
            try:
                self.queue.put(value, timeout=0.2)
                return
            except Full:
                pass

    def _decode(self):
        capture = cv2.VideoCapture()
        try:
            # Network timeouts are supported by OpenCV's FFmpeg backend.
            if isinstance(self.source, str) and self.source.startswith(('rtsp://', 'https://', 'http://')):
                capture.open(self.source, cv2.CAP_FFMPEG, [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 10000, cv2.CAP_PROP_READ_TIMEOUT_MSEC, 10000])
            else:
                capture.open(self.source)
            if not capture.isOpened():
                raise ValueError('Cannot open this video source.')
            fps = capture.get(cv2.CAP_PROP_FPS)
            self.fps = fps if 1 <= fps <= 240 else 30.0
            self.total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT)) if not self.live else 0
            size = max(1, round(self.fps * self.chunk_seconds))
            overlap = max(0, min(size - 1, round(self.fps * self.overlap_seconds)))
            frames, index, chunk_id = [], 0, 0
            last_time = -1.0
            start = time.monotonic()
            while not self.stop.is_set():
                ok, image = capture.read()
                if not ok:
                    break
                if max(image.shape[:2]) > self.max_width:
                    scale = self.max_width / max(image.shape[:2])
                    # Even dimensions are required by H.264's YUV420 encoder.
                    image = cv2.resize(image, (max(2, int(image.shape[1]*scale)//2*2), max(2, int(image.shape[0]*scale)//2*2)))
                timestamp = time.monotonic() - start if self.live else capture.get(cv2.CAP_PROP_POS_MSEC) / 1000
                if timestamp <= last_time:
                    timestamp = max(index / self.fps, last_time + 1 / self.fps)
                last_time = timestamp
                # Store compressed chunk frames. Ten seconds of raw HD frames
                # would otherwise consume hundreds of MB per queue entry.
                ok, encoded = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 93])
                if not ok:
                    raise ValueError('Could not buffer a decoded frame.')
                frames.append(Frame(index, timestamp, encoded))
                index += 1
                if len(frames) == size:
                    self._put(Chunk(chunk_id, frames))
                    frames = frames[-overlap:] if overlap else []
                    chunk_id += 1
            if frames and (chunk_id == 0 or len(frames) > overlap):
                self._put(Chunk(chunk_id, frames))
            self._put(None)
        except Exception as exc:
            self._put(exc)
        finally:
            capture.release()

    def __iter__(self):
        thread = Thread(target=self._decode, daemon=True)
        thread.start()
        try:
            while True:
                item = self.queue.get()
                if item is None:
                    break
                if isinstance(item, Exception):
                    raise item
                # Expand lazily while the consumer iterates, retaining compressed
                # overlap frames in the queue. State still belongs to the session.
                item.frames = LazyFrames(item.frames)
                yield item
        finally:
            self.stop.set()
            thread.join(timeout=1)


class LazyFrames:
    def __init__(self, compressed):
        self.compressed = compressed

    def __len__(self):
        return len(self.compressed)

    def __iter__(self):
        for item in self.compressed:
            image = cv2.imdecode(item.image, cv2.IMREAD_COLOR)
            if image is None:
                raise ValueError('Could not decode a buffered frame.')
            yield Frame(item.index, item.time, image)

class ActivityGate:
    """Conservative motion gate with hysteresis and periodic idle probes."""
    def __init__(self):
        self.previous = None
        self.active_until = 0.0
        self.next_probe = 0.0
        self.state = 'possible play'

    def inspect(self, frame, corners=None):
        gray = cv2.cvtColor(cv2.resize(frame.image, (240, 135)), cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        motion = 1.0
        if self.previous is not None:
            changed = cv2.absdiff(gray, self.previous) > 14
            if corners:
                mask = np.zeros(gray.shape, np.uint8)
                cv2.fillConvexPoly(mask, (np.array(corners) * [240, 135]).astype(np.int32), 1)
                motion = float(changed[mask > 0].mean()) if mask.any() else 1.0
            else:
                motion = float(changed.mean())
        self.previous = gray
        if motion > 0.008:
            self.active_until = frame.time + 1.5
            self.state = 'active play' if motion < 0.65 else 'possible play'
        active = frame.time <= self.active_until
        probe = frame.time >= self.next_probe
        if probe:
            self.next_probe = frame.time + 2.0
        if not active:
            self.state = 'idle'
        return active or probe, motion
