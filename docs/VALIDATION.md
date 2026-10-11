# Validation record

Build date: 10 October 2026.

## Confirmed

- React/TypeScript production build passed.
- 18 regression tests passed: tennis deuce/advantage/tiebreak/match, badminton deuce/30-point cap/match, grounded contact rules, unknown landings, confidence propagation, overlap continuity, timestamps, activity probes, court mapping, player identity, missing-detection gaps, duplicate points, undo, invalid uploads, credential omission and atomic session claims.
- All seven exact reference release files downloaded. SHA-256 provenance is in `weights/manifest.json`.
- Real tennis and badminton object models each returned an object detection on a reference frame.
- YOLO Nano and YOLO Small pose returned a player on the tested frame. RTMPose returned four person poses; RTMO executed successfully but returned no person above its threshold on that frame. This is an inference compatibility test, not an accuracy benchmark.
- Both sports completed 12-frame processing runs and exported H.264 MP4 plus per-frame JSONL. Detailed timings and session identifiers are in `smoke-results.json`. These short tests do not establish real-time throughput or full-match accuracy.
- Browser inspection confirmed the dashboard layout, saved-session navigation, annotated video display, point addition and undo.
- A real HTTP integration check uploaded a clip, started queued inference, rejected a duplicate start with HTTP 409, processed all 12 frames, and served the exported MP4 with HTTP 206 range support for browser seeking.

## Limits of this validation

- CPU execution was available; GPU inference was not measured.
- External live cameras, Docker/Redis/PostgreSQL deployment and full-match throughput were not exercised on this host.
- Court suggestions are heuristic and require review. Court-plane projection passed synthetic geometry tests; physical measurement accuracy was not benchmarked.
- Video-only scoring remains assisted. Image-space contact candidates do not establish ground contact. The rules engine's automatic scoring was tested with explicit, high-confidence grounded observations.
- Starlette emitted one compatibility deprecation warning for its HTTPX test client; all tests passed.
- Windows sandbox socket restrictions prevented asynchronous API tests and server startup inside the sandbox. The same tests passed and the localhost server started when run with approved local socket access.
