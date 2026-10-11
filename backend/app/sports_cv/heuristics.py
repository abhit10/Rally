import numpy as np
from .schemas import StrokeEvaluation


def calculate_angle(a, b, c) -> float:
    """Calculates the angle (in degrees) formed by three keypoints (a, b, c) with b as the vertex."""
    a = np.array(a)
    b = np.array(b)
    c = np.array(c)

    radians = np.arctan2(c[1] - b[1], c[0] - b[0]) - np.arctan2(a[1] - b[1], a[0] - b[0])
    angle = np.abs(radians * 180.0 / np.pi)
    if angle > 180.0:
        angle = 360.0 - angle
    return float(angle)


def classify_and_evaluate_stroke(keypoints_xy) -> StrokeEvaluation:
    """
    Pure heuristics function for Badminton stroke classification and biomechanical form scoring.
    Accepts keypoints array (COCO-17 format or similar 2D array/tensor).
    Returns a StrokeEvaluation object containing (stroke_type, score, feedback).
    """
    try:
        if keypoints_xy is None or len(keypoints_xy) < 13:
            return StrokeEvaluation(
                stroke_type="Unknown Badminton Action",
                score=0,
                feedback="No clear player detected",
            )

        r_shoulder = keypoints_xy[6]
        r_elbow = keypoints_xy[8]
        r_wrist = keypoints_xy[10]
        r_hip = keypoints_xy[12]

        if (
            any(np.isnan(r_shoulder))
            or any(np.isnan(r_elbow))
            or any(np.isnan(r_wrist))
        ):
            return StrokeEvaluation(
                stroke_type="Unknown Badminton Action",
                score=0,
                feedback="Player pose partially occluded",
            )

        wrist_y = r_wrist[1]
        shoulder_y = r_shoulder[1]
        hip_y = r_hip[1]

        # 1. Badminton Overhead Smash / Clear / Drop Heuristics
        if wrist_y < shoulder_y:
            elevation_angle = calculate_angle(r_hip, r_shoulder, r_elbow)
            elbow_angle = calculate_angle(r_shoulder, r_elbow, r_wrist)

            # Check if high-elevation jump smash or steep smash contact
            if elevation_angle > 75 and elbow_angle > 140:
                stroke_type = "Badminton Jump Smash"
                score = 100
                feedback = "Excellent high-contact badminton smash extension!"
            else:
                stroke_type = "Badminton Overhead Clear / Drop"
                score = 100
                feedback = "Good overhead high-point shuttle contact."

            if elevation_angle < 65:
                score -= 30
                feedback = "Raise your hitting elbow higher before shuttle contact."
            if elbow_angle < 110:
                score -= 25
                feedback = "Extend your racket arm fully for maximum power & reach."

        # 2. Badminton Net Play / Defensive Lift / Underhand Serve
        elif shoulder_y <= wrist_y <= hip_y + 50:
            stroke_type = "Badminton Net Lift / Defensive Block"
            knee_angle = (
                calculate_angle(keypoints_xy[12], keypoints_xy[14], keypoints_xy[16])
                if len(keypoints_xy) > 16 and not any(np.isnan(keypoints_xy[14])) and not any(np.isnan(keypoints_xy[16]))
                else 180.0
            )

            score = 100
            feedback = "Solid low defense and net control stance."
            if knee_angle > 155:
                score -= 25
                feedback = "Lunge deeper with lead knee bent for better net reach & court coverage."

        # 3. Badminton Backhand Drive / Cross-court Defense
        else:
            stroke_type = "Badminton Backhand Drive / Defense"
            score = 90
            feedback = "Good backhand grip alignment & stable balance base."

        return StrokeEvaluation(
            stroke_type=stroke_type,
            score=max(0, score),
            feedback=feedback,
        )

    except (IndexError, TypeError, ValueError):
        return StrokeEvaluation(
            stroke_type="Unknown Badminton Action",
            score=0,
            feedback="No clear player detected",
        )
