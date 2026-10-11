import threading
from pathlib import Path
from typing import Optional
from ultralytics import YOLO

from .config import get_weights_path

_model_lock = threading.Lock()
_cached_model: Optional[YOLO] = None
_cached_weights_path: Optional[str] = None


def get_pose_model(weights_path: Optional[str] = None) -> YOLO:
    """
    Lazy-loads and caches the YOLO pose model on first call.
    Avoids any import-time model initialization side effects.
    """
    global _cached_model, _cached_weights_path

    resolved_path = Path(weights_path) if weights_path else get_weights_path()
    path_str = str(resolved_path)

    if _cached_model is not None and _cached_weights_path == path_str:
        return _cached_model

    with _model_lock:
        if _cached_model is not None and _cached_weights_path == path_str:
            return _cached_model

        if not resolved_path.is_file():
            raise FileNotFoundError(f"YOLO pose weights file not found at: '{path_str}'")

        model = YOLO(path_str)
        _cached_model = model
        _cached_weights_path = path_str
        return model


def reset_model_cache():
    """Utility to reset model cache (used in testing or re-initialization)."""
    global _cached_model, _cached_weights_path
    with _model_lock:
        _cached_model = None
        _cached_weights_path = None
