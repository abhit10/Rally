from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .analyzer import analyze_video
from .config import SPORTS_CV_ENABLED
from .schemas import VideoAnalysis

router = APIRouter(prefix="/api/sports-cv", tags=["sports-cv"])


class AnalyzeRequest(BaseModel):
    video_path: str = Field(..., description="Path to the video file to analyze")


@router.post("/analyze", response_model=VideoAnalysis)
def analyze(request: AnalyzeRequest):
    """
    Analyzes a video file for stroke classification and form scoring.
    Feature-flagged via SPORTS_CV_ENABLED.
    """
    if not SPORTS_CV_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Sports CV service is currently disabled (SPORTS_CV_ENABLED=false)",
        )

    analysis = analyze_video(request.video_path)
    if analysis.error:
        raise HTTPException(status_code=400, detail=analysis.error)

    return analysis
