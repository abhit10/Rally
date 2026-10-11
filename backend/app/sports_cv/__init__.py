"""
Sports CV Worker integration module for Racket Intelligence.
Isolated package for video stroke classification and form evaluation.
"""

from .analyzer import analyze_video
from .config import SPORTS_CV_ENABLED
from .schemas import Detection, FrameResult, VideoAnalysis, StrokeEvaluation

__all__ = [
    "analyze_video",
    "SPORTS_CV_ENABLED",
    "Detection",
    "FrameResult",
    "VideoAnalysis",
    "StrokeEvaluation",
]
