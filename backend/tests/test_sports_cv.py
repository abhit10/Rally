import json
import math
import os
import tempfile
from pathlib import Path
import numpy as np
import pytest

from backend.app.sports_cv.heuristics import classify_and_evaluate_stroke, calculate_angle
from backend.app.sports_cv.schemas import StrokeEvaluation, VideoAnalysis
from backend.app.sports_cv.analyzer import analyze_video
from backend.app.sports_cv.config import SPORTS_CV_ENABLED
from backend.app.sports_cv.model_loader import reset_model_cache, get_pose_model


# =====================================================================
# a) Unit tests for the heuristics function
# =====================================================================
def test_heuristics_missing_or_short_keypoints():
    eval1 = classify_and_evaluate_stroke(None)
    assert eval1.stroke_type == "Unknown Badminton Action"
    assert eval1.score == 0
    assert eval1.feedback == "No clear player detected"

    eval2 = classify_and_evaluate_stroke([])
    assert eval2.stroke_type == "Unknown Badminton Action"
    assert eval2.score == 0

    eval3 = classify_and_evaluate_stroke([[0, 0]] * 5)  # Less than 13 keypoints
    assert eval3.stroke_type == "Unknown Badminton Action"
    assert eval3.score == 0


def test_heuristics_nan_keypoints():
    keypoints = np.zeros((17, 2))
    keypoints[6] = [100, np.nan]  # r_shoulder NaN
    eval_res = classify_and_evaluate_stroke(keypoints)
    assert eval_res.stroke_type == "Unknown Badminton Action"
    assert eval_res.score == 0
    assert eval_res.feedback == "Player pose partially occluded"


def test_heuristics_jump_smash():
    # Construct keypoints for wrist above shoulder, elevation > 75, elbow > 140
    # r_shoulder = [100, 200], r_hip = [100, 300], r_elbow = [200, 190], r_wrist = [300, 180]
    keypoints = np.zeros((17, 2))
    keypoints[6] = [100, 200]  # r_shoulder
    keypoints[8] = [200, 190]  # r_elbow
    keypoints[10] = [300, 180]  # r_wrist (wrist_y = 180 < shoulder_y = 200)
    keypoints[12] = [100, 300]  # r_hip

    eval_res = classify_and_evaluate_stroke(keypoints)
    assert eval_res.stroke_type == "Badminton Jump Smash"
    assert eval_res.score == 100
    assert "smash extension" in eval_res.feedback


def test_heuristics_overhead_penalties():
    # wrist above shoulder, elevation < 65 (-30 penalty), elbow < 110 (-25 penalty) -> score 45
    # r_shoulder=[100,200], r_hip=[100,300], r_elbow=[110,250] (low elevation), r_wrist=[120,180]
    keypoints = np.zeros((17, 2))
    keypoints[6] = [100, 200]
    keypoints[8] = [110, 250]
    keypoints[10] = [120, 180]
    keypoints[12] = [100, 300]

    eval_res = classify_and_evaluate_stroke(keypoints)
    assert eval_res.stroke_type == "Badminton Overhead Clear / Drop"
    assert eval_res.score < 100
    assert "elbow higher" in eval_res.feedback or "fully" in eval_res.feedback


def test_heuristics_net_lift():
    # shoulder_y <= wrist_y <= hip_y + 50
    # shoulder_y = 100, hip_y = 300, wrist_y = 200
    keypoints = np.zeros((17, 2))
    keypoints[6] = [100, 100]  # r_shoulder
    keypoints[8] = [150, 150]  # r_elbow
    keypoints[10] = [200, 200]  # r_wrist
    keypoints[12] = [100, 300]  # r_hip
    keypoints[14] = [100, 400]  # r_knee
    keypoints[16] = [100, 500]  # r_ankle (straight knee, knee_angle = 180 > 155 -> penalty -25)

    eval_res = classify_and_evaluate_stroke(keypoints)
    assert eval_res.stroke_type == "Badminton Net Lift / Defensive Block"
    assert eval_res.score == 75
    assert "Lunge deeper" in eval_res.feedback


def test_heuristics_backhand_drive():
    # wrist_y > hip_y + 50 -> Backhand Drive / Defense, score 90
    keypoints = np.zeros((17, 2))
    keypoints[6] = [100, 100]  # r_shoulder
    keypoints[8] = [150, 200]  # r_elbow
    keypoints[10] = [200, 400]  # r_wrist (wrist_y = 400 > hip_y + 50 = 350)
    keypoints[12] = [100, 300]  # r_hip

    eval_res = classify_and_evaluate_stroke(keypoints)
    assert eval_res.stroke_type == "Badminton Backhand Drive / Defense"
    assert eval_res.score == 90
    assert "backhand grip" in eval_res.feedback


def test_heuristics_boundary_values():
    # Angle boundary helper tests
    angle_straight = calculate_angle([0, 0], [0, 1], [0, 2])
    assert math.isclose(angle_straight, 180.0, abs_tol=1e-3)

    angle_right = calculate_angle([1, 0], [0, 0], [0, 1])
    assert math.isclose(angle_right, 90.0, abs_tol=1e-3)


# =====================================================================
# b) Golden / Regression tests against sports-cv-worker baseline outputs
# =====================================================================
def _find_path(relative_str: str) -> Path:
    candidates = [
        Path(relative_str),
        Path("..") / relative_str,
        Path("../..") / relative_str,
        Path("d:/me/New folder (3)") / relative_str.lstrip("../"),
        Path("d:/me/New folder (3)/sports-cv-worker") / relative_str.split("sports-cv-worker/")[-1] if "sports-cv-worker/" in relative_str else Path(relative_str),
    ]
    for c in candidates:
        if c.exists():
            return c
    return Path(relative_str)

BADMINTON_SAMPLE = _find_path("sports-cv-worker/samples/badminton_rally.mp4")
BADMINTON_BASELINE = _find_path("sports-cv-worker/outputs/badminton_stroke_analysis.json")

TENNIS_SAMPLE = _find_path("sports-cv-worker/samples/tennis_rally.mp4")
TENNIS_BASELINE = _find_path("sports-cv-worker/outputs/stroke_analysis.json")


@pytest.mark.skipif(not BADMINTON_SAMPLE.is_file(), reason="Badminton sample video not found")
def test_golden_badminton_analysis():
    weights_path = _find_path("weights/yolo26n-pose.pt")


    analysis = analyze_video(str(BADMINTON_SAMPLE), weights_path=str(weights_path))
    assert analysis.error is None
    assert analysis.frames_analyzed == 36
    assert math.isclose(analysis.duration_seconds, 17.58, abs_tol=0.1)

    if BADMINTON_BASELINE.is_file():
        with BADMINTON_BASELINE.open("r", encoding="utf-8") as f:
            expected_json = json.load(f)

        assert len(analysis.frames) == len(expected_json["frames"])
        for idx, (actual_frame, expected_frame) in enumerate(zip(analysis.frames, expected_json["frames"])):
            assert math.isclose(actual_frame.timestamp, expected_frame["timestamp"], abs_tol=0.01)
            assert len(actual_frame.objects) == len(expected_frame["objects"])
            if actual_frame.objects and expected_frame["objects"]:
                actual_obj = actual_frame.objects[0]
                expected_obj = expected_frame["objects"][0]
                assert actual_obj.object == expected_obj["object"]
                assert math.isclose(actual_obj.confidence, expected_obj["confidence"], abs_tol=0.05)


@pytest.mark.skipif(not TENNIS_SAMPLE.is_file(), reason="Tennis sample video not found")
def test_golden_tennis_analysis():
    weights_path = _find_path("weights/yolo26n-pose.pt")

    analysis = analyze_video(str(TENNIS_SAMPLE), weights_path=str(weights_path))

    assert analysis.error is None
    assert analysis.frames_analyzed == 95
    assert math.isclose(analysis.duration_seconds, 45.57, abs_tol=0.1)

    if TENNIS_BASELINE.is_file():
        with TENNIS_BASELINE.open("r", encoding="utf-8") as f:
            expected_json = json.load(f)

        # Note: per spec limitation 3, tennis labels in stroke_analysis.json came from an earlier version of detector.py
        # Current detector.py produces badminton heuristics on tennis video. We verify frame count, timestamps, and bounding box structure.
        assert len(analysis.frames) == len(expected_json["frames"])
        for actual_frame, expected_frame in zip(analysis.frames, expected_json["frames"]):
            assert math.isclose(actual_frame.timestamp, expected_frame["timestamp"], abs_tol=0.01)
            assert len(actual_frame.objects) == len(expected_frame["objects"])
            if actual_frame.objects:
                assert actual_frame.objects[0].confidence > 0.0
                assert len(actual_frame.objects[0].bbox) == 4



# =====================================================================
# c) Failure tests
# =====================================================================
def test_failure_nonexistent_video():
    analysis = analyze_video("nonexistent_video_12345.mp4")
    assert analysis.error is not None
    assert "not found" in analysis.error
    assert analysis.frames_analyzed == 0


def test_failure_corrupt_video():
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        f.write(b"NOT A VALID MP4 VIDEO CONTENT")
        temp_path = f.name

    try:
        analysis = analyze_video(temp_path)
        assert analysis.error is not None
        assert "Could not open" in analysis.error or "Invalid or corrupted" in analysis.error
        assert analysis.frames_analyzed == 0
    finally:
        os.unlink(temp_path)


def test_failure_missing_weights():
    reset_model_cache()
    analysis = analyze_video(
        str(BADMINTON_SAMPLE) if BADMINTON_SAMPLE.is_file() else "test.mp4",
        weights_path="nonexistent_weights_999.pt",
    )
    assert analysis.error is not None
    assert "not found" in analysis.error


def test_failure_empty_video():
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        temp_path = f.name
        # Write 0 bytes — an empty file

    try:
        analysis = analyze_video(temp_path)
        assert analysis.error is not None
        assert analysis.frames_analyzed == 0
    finally:
        os.unlink(temp_path)


# =====================================================================
# e) Confirm feature flag OFF behavior
# =====================================================================
def test_feature_flag_default():
    assert SPORTS_CV_ENABLED is False


def test_host_routes_unaffected_with_flag_off():
    """With SPORTS_CV_ENABLED=False (default), the sports-cv router must NOT be registered."""
    from fastapi.testclient import TestClient
    from backend.app.main import app

    client = TestClient(app)

    # Existing health endpoint still works
    resp = client.get("/api/health")
    assert resp.status_code == 200

    # Sports CV endpoint should NOT be registered.
    # Expect 404 (no route) or 405 (catch-all static mount rejects POST).
    # Critically, it must NOT be 503 (which the router guard would return).
    resp = client.post("/api/sports-cv/analyze", json={"video_path": "test.mp4"})
    assert resp.status_code in (404, 405), (
        f"Expected 404/405 (route not registered), got {resp.status_code}"
    )

