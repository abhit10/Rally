import os
from pathlib import Path

# Feature flag: default False for dark shipping / safe rollback
SPORTS_CV_ENABLED: bool = os.getenv("SPORTS_CV_ENABLED", "false").lower() in ("true", "1", "yes")

# Model weights path (configurable, with fallbacks)
DEFAULT_WEIGHTS_PATHS = [
    Path(os.getenv("SPORTS_CV_WEIGHTS_PATH", "weights/yolo26n-pose.pt")),
    Path("weights/yolo26n-pose.pt"),
    Path("../sports-cv-worker/yolo26n-pose.pt"),
    Path("../../sports-cv-worker/yolo26n-pose.pt"),
]

def get_weights_path() -> Path:
    env_path = os.getenv("SPORTS_CV_WEIGHTS_PATH")
    if env_path:
        return Path(env_path)
    for path in DEFAULT_WEIGHTS_PATHS:
        if path.is_file():
            return path
    return DEFAULT_WEIGHTS_PATHS[0]

# Confidence threshold for YOLO detection
SPORTS_CV_CONF_THRESHOLD: float = float(os.getenv("SPORTS_CV_CONF_THRESHOLD", "0.25"))

# Sampling interval in seconds
SPORTS_CV_FRAME_INTERVAL_SECONDS: float = float(os.getenv("SPORTS_CV_FRAME_INTERVAL_SECONDS", "0.5"))

# Resource limits
SPORTS_CV_MAX_DURATION_SECONDS: float = float(os.getenv("SPORTS_CV_MAX_DURATION_SECONDS", "600.0"))
SPORTS_CV_MAX_FILE_SIZE_BYTES: int = int(os.getenv("SPORTS_CV_MAX_FILE_SIZE_BYTES", str(2 * 1024 * 1024 * 1024))) # 2 GB
