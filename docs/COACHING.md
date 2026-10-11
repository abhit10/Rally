# Coaching reports

Restart the API and any Celery worker after updating Python code. Run `npm run build` in `frontend`, then reload the dashboard. Choose Balanced, Fast Mode or Deep Analysis when creating a session. Mark the four singles-court corners in the displayed order before starting analysis.

The Tactical Report uses version 2 analytics. Previously saved sessions remain playable, but must be analyzed in a new session to obtain these measurements. Older distance estimates are deliberately hidden. Missing measurements appear as a dash, never as zero.

## Player recovery and badminton coaching mode

Badminton sessions no longer award points. Manual point entry and undo endpoints reject badminton requests, observation submissions do not confirm winners, and video analysis stores unscored rally observations. The dashboard replaces its badminton scoreboard with a coaching notebook. Previously exported videos are unchanged; analyze the recording again to produce the new overlays and player coverage.

The detector retains the exact reference weights. Balanced analysis now uses a more detailed full-frame pose pass, followed by a far-court crop. Without an outline it uses overlapping upper-court views. Crop detections are returned to original image coordinates, clipped people are rejected, and duplicate boxes are merged. This adds inference work in exchange for better small-player visibility; it is not a retrained model.

A provisional visible-court outline can exclude officials and spectators during player selection. Only user-confirmed corners supply physical movement measurements. The identity tracker accepts consistent lower-confidence players and can reacquire a nearby player after a short loss even when the underlying tracking ID changes. Missing positions remain missing; they never become invented movement.

The coaching notebook reports how often each player was visible in reviewed moments, warns when less than 70% of checks show a player, and provides video links for the longest completed rally and sustained movement bursts. Compare workloads only when both players have good coverage. Physical effort totals may still be understated during occlusion or camera cuts.

Run `scripts/check_player_recall.py --source path/to/match.mp4` with the project Python environment to produce a paired before/after detection contact sheet. Inspect the boxes against the actual players. Detection counts and confidence are not accuracy measurements without human labels.

## Measurement definitions

- Distance: observed foot positions mapped through the calibrated court homography, accumulated in meters. No calibration means no distance. Gaps over 0.5 seconds, changed tracking identities, interpolated frames and jumps above 12 m/s do not add distance.
- Net play: time spent in the front 35% of either half, measured from the net. Rear court is the remaining 65%. Percentages use observed rally time inside the court, not frame counts. They describe positioning, not proven tactical dominance or point-winning causation.
- Sprints: speeds above 3.2 m/s sustained for at least 0.3 seconds during a rally. A burst rearms after 0.3 seconds below 2.7 m/s. High-intensity share is time above 3.2 m/s divided by observed rally movement time.
- Rally duration: first accepted hit to the rally decision. Only completed rally decisions contribute; interrupted and unfinished rallies are excluded. Shot counts remain detected contacts, so missed contacts affect pace and distribution.
- Rally distribution: short is 1–4 shots, medium is 5–10, marathon is 11 or more. Four-shot rallies are included explicitly.
- Work-to-rest ratio: total completed rally duration divided by observed recovery between completed rallies. Cutaways and interrupted rallies break recovery continuity. This is workload context, not a fatigue diagnosis.
- Rally pace: inter-hit intervals per minute across completed rally time. It describes exchange tempo and is not ball velocity.

## Shot speed and other limits

A court homography maps ground positions; applying it to an airborne ball or shuttle does not recover its true distance or speed. The dashboard therefore leaves peak shot speed unavailable with the current camera pipeline. `AnalyticsEngine.observe_metric_shot` accepts independently validated 3D positions in meters, with timestamps and a persistent identity, and converts their displacement to km/h. It is an extension point, not a claim that this pipeline reconstructs 3D flight.

No energy expenditure, medical fatigue assessment, stroke classification or forced-backhand claim is invented from player positions. Deep Analysis provides denser pose observations for coach-led video review; it does not automatically grade technique. Camera movement invalidates a fixed court calibration; use a stable full-court recording. Close calls and uncertain rally outcomes still need review.

## Validation

From `backend`, run `../.venv/Scripts/python.exe -m pytest -q`. From `frontend`, run `npm run build`. Coaching tests cover metric mapping, mirrored zones, time weighting, sprint hysteresis, missing calibration, identity changes, interpolation, interrupted rallies, recovery, duplicate decisions and validated flight speed. Existing scoring and session-deletion tests remain in the suite.
