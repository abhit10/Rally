from typing import List, Optional
from pydantic import BaseModel, Field


class StrokeEvaluation(BaseModel):
    stroke_type: str
    score: int
    feedback: str

    def to_legacy_object_string(self) -> str:
        return f"Stroke: {self.stroke_type} | Score: {self.score} | Feedback: {self.feedback}"


class Detection(BaseModel):
    object: str
    confidence: float
    bbox: List[float]
    
    # Optional typed extensions (populated alongside legacy string)
    stroke_type: Optional[str] = None
    score: Optional[int] = None
    feedback: Optional[str] = None


class FrameResult(BaseModel):
    timestamp: float
    objects: List[Detection]


class VideoAnalysis(BaseModel):
    video_path: str
    duration_seconds: float
    frames_analyzed: int
    frames: List[FrameResult]
    error: Optional[str] = None
