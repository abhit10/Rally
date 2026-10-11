import os
from pathlib import Path
from typing import Optional
import cv2

from .config import (
    SPORTS_CV_CONF_THRESHOLD,
    SPORTS_CV_FRAME_INTERVAL_SECONDS,
    SPORTS_CV_MAX_DURATION_SECONDS,
    SPORTS_CV_MAX_FILE_SIZE_BYTES,
)
from .heuristics import classify_and_evaluate_stroke
from .model_loader import get_pose_model
from .schemas import Detection, FrameResult, VideoAnalysis


def analyze_video(
    video_path: str,
    weights_path: Optional[str] = None,
    conf_threshold: Optional[float] = None,
    frame_interval_seconds: Optional[float] = None,
) -> VideoAnalysis:
    """
    Analyzes a video file to detect sports keypoints and classify per-frame stroke/form.
    Streams video frame-by-frame, enforces safety bounds, and releases resources cleanly.
    """
    path = Path(video_path)
    if not path.is_file():
        return VideoAnalysis(
            video_path=video_path,
            duration_seconds=0.0,
            frames_analyzed=0,
            frames=[],
            error=f"Video file not found or unreadable: '{video_path}'",
        )

    # Check file size limit for resource safety
    try:
        file_size = path.stat().st_size
        if file_size > SPORTS_CV_MAX_FILE_SIZE_BYTES:
            return VideoAnalysis(
                video_path=video_path,
                duration_seconds=0.0,
                frames_analyzed=0,
                frames=[],
                error=f"Video file size ({file_size} bytes) exceeds safety limit ({SPORTS_CV_MAX_FILE_SIZE_BYTES} bytes)",
            )
    except OSError as e:
        return VideoAnalysis(
            video_path=video_path,
            duration_seconds=0.0,
            frames_analyzed=0,
            frames=[],
            error=f"Error checking video file size: {e}",
        )

    # Lazy load model with graceful failure on missing weights
    conf = conf_threshold if conf_threshold is not None else SPORTS_CV_CONF_THRESHOLD
    interval = frame_interval_seconds if frame_interval_seconds is not None else SPORTS_CV_FRAME_INTERVAL_SECONDS

    try:
        model = get_pose_model(weights_path)
    except Exception as exc:
        return VideoAnalysis(
            video_path=video_path,
            duration_seconds=0.0,
            frames_analyzed=0,
            frames=[],
            error=f"Model initialization failed: {exc}",
        )

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return VideoAnalysis(
            video_path=video_path,
            duration_seconds=0.0,
            frames_analyzed=0,
            frames=[],
            error=f"Could not open video stream: '{video_path}'",
        )

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    if fps <= 0 or total_frames <= 0:
        cap.release()
        return VideoAnalysis(
            video_path=video_path,
            duration_seconds=0.0,
            frames_analyzed=0,
            frames=[],
            error="Invalid or corrupted video (FPS <= 0 or frame count <= 0)",
        )

    duration = total_frames / fps

    if duration > SPORTS_CV_MAX_DURATION_SECONDS:
        cap.release()
        return VideoAnalysis(
            video_path=video_path,
            duration_seconds=round(duration, 2),
            frames_analyzed=0,
            frames=[],
            error=f"Video duration ({duration:.2f}s) exceeds safety limit ({SPORTS_CV_MAX_DURATION_SECONDS}s)",
        )

    frame_step = max(1, round(fps * interval))
    frames = []
    frame_index = 0

    try:
        while True:
            success, frame = cap.read()
            if not success:
                break

            if frame_index % frame_step == 0:
                timestamp = frame_index / fps
                results = model.predict(source=frame, conf=conf, verbose=False)

                detections = []
                for result in results:
                    if result.keypoints is not None and len(result.keypoints.xy) > 0:
                        person_keypoints = result.keypoints.xy[0].cpu().numpy()
                        stroke_eval = classify_and_evaluate_stroke(person_keypoints)

                        confidence = 1.0
                        bbox = []
                        if result.boxes is not None and len(result.boxes) > 0:
                            confidence = round(float(result.boxes.conf[0]), 3)
                            bbox = [round(v, 2) for v in result.boxes.xyxy[0].tolist()]

                        detections.append(
                            Detection(
                                object=stroke_eval.to_legacy_object_string(),
                                confidence=confidence,
                                bbox=bbox,
                                stroke_type=stroke_eval.stroke_type,
                                score=stroke_eval.score,
                                feedback=stroke_eval.feedback,
                            )
                        )

                frames.append(
                    FrameResult(
                        timestamp=round(timestamp, 2),
                        objects=detections,
                    )
                )
            frame_index += 1
    except Exception as exc:
        return VideoAnalysis(
            video_path=video_path,
            duration_seconds=round(duration, 2),
            frames_analyzed=len(frames),
            frames=frames,
            error=f"Processing interrupted: {exc}",
        )
    finally:
        cap.release()

    return VideoAnalysis(
        video_path=video_path,
        duration_seconds=round(duration, 2),
        frames_analyzed=len(frames),
        frames=frames,
    )
