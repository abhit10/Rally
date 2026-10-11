# Sports CV Worker Module (`backend/app/sports_cv`)

Integrated per-frame sports stroke classification and biomechanical form scoring worker.

## Quick Start & Enabling the Feature

By default, the feature is disabled (`SPORTS_CV_ENABLED=false`) for safe dark-shipping.

To enable in development or production, set environment variable:
```bash
export SPORTS_CV_ENABLED=true
```

## Configuration Reference

| Environment Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `SPORTS_CV_ENABLED` | bool | `false` | Master feature flag for dark shipping and instant rollback |
| `SPORTS_CV_WEIGHTS_PATH` | str | `weights/yolo26n-pose.pt` | Path to YOLO pose weights file |
| `SPORTS_CV_CONF_THRESHOLD` | float | `0.25` | Confidence threshold for person pose detection |
| `SPORTS_CV_FRAME_INTERVAL_SECONDS` | float | `0.5` | Sampling interval between analyzed frames |
| `SPORTS_CV_MAX_DURATION_SECONDS` | float | `600.0` | Safety limit on maximum video duration (in seconds) |
| `SPORTS_CV_MAX_FILE_SIZE_BYTES` | int | `2147483648` (2GB) | Safety limit on maximum video file size (in bytes) |

## REST API Endpoint

When `SPORTS_CV_ENABLED=true`, the endpoint is available at:
`POST /api/sports-cv/analyze`

**Request Payload:**
```json
{
  "video_path": "samples/badminton_rally.mp4"
}
```

**Response Format (Frozen Output Contract):**
```json
{
  "video_path": "samples/badminton_rally.mp4",
  "duration_seconds": 17.58,
  "frames_analyzed": 36,
  "frames": [
    {
      "timestamp": 0.0,
      "objects": [
        {
          "object": "Stroke: Badminton Net Lift / Defensive Block | Score: 75 | Feedback: Lunge deeper with lead knee bent for better net reach & court coverage.",
          "confidence": 0.847,
          "bbox": [579.64, 393.75, 676.31, 621.5],
          "stroke_type": "Badminton Net Lift / Defensive Block",
          "score": 75,
          "feedback": "Lunge deeper with lead knee bent for better net reach & court coverage."
        }
      ]
    }
  ]
}
```

## Rollback Procedure

1. **Instant Soft Rollback**: Set `SPORTS_CV_ENABLED=false`. All host application routes, workers, and startup paths will completely bypass `sports_cv` model loading and execution.
2. **Complete Code Rollback**:
   - Remove `backend/app/sports_cv/` directory.
   - Remove `backend/tests/test_sports_cv.py`.
   - Revert registration lines in `backend/app/main.py`.
