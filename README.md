# Rally — Unified Racket Intelligence

A tennis and badminton analysis prototype with a React dashboard, FastAPI service and shared Python vision engine. No reference UI or application code is copied.

## Repository setup

Submission repository: [ELEVATE-1-0/ELEV15](https://github.com/ELEVATE-1-0/ELEV15) (private).
See [the submission guide](docs/SUBMISSION.md) for push instructions.

This repository contains source, dependency manifests, tests and documentation.
Virtual environments, uploaded videos, session databases, generated dashboards and
model binaries stay local. Follow **Fresh installation** after cloning; model
downloads are required for video analysis.

## Start on this Windows computer

After completing the fresh installation below, run from the repository root:

```powershell
./scripts/start.ps1
```

Open http://127.0.0.1:8000. API documentation is at http://127.0.0.1:8000/docs.

1. Select Tennis or Badminton and upload a video.
2. Mark the **singles** court corners in order: far-left, far-right, near-right, near-left. If automatic court suggestions appear, inspect them first. Click again after four points to restart selection. Court dimensions assume the singles boundaries, not doubles sidelines.
3. Click **Analyze**. The latest processed frame, estimated hits, activity filtering, motion metrics and event candidates update during processing.
4. Play the completed annotated video. Review contact candidates before awarding a point to A or B. The score ledger supports corrections and undo.
5. Download the annotated MP4 or frame-level JSONL analysis.

Player A starts on the near side and Player B on the far side. Identity association persists across frames; long occlusions and changes of ends can require a new session. Keep the camera fixed with the entire court visible.

For a live feed, use **New session → Connect camera** with an RTSP/IP-camera URL or `camera:0` for the server's webcam. Phone capture requires an IP-camera feed; direct browser camera streaming is not implemented. Stop a live session to finalize its annotated video. Live streams currently run without interactive court calibration, so movement metrics remain unavailable unless corners are supplied through the API.

## Fresh installation

Use Python 3.12 and Node.js 22 or newer. Do not use the system Python 3.14 for this environment.

```powershell
py -3.12 -m venv .venv
.venv/Scripts/python.exe -m pip install -r backend/requirements-vision.txt
.venv/Scripts/python.exe scripts/download_models.py
cd frontend
npm ci
npm run build
cd ..
./scripts/start.ps1
```

Local mode uses SQLite and one session worker, with a separate bounded decoder thread. It does not require Redis or Docker. Model inference starts only after analysis is requested; missing weights are reported explicitly.

For dashboard development, run the API and `npm run dev` inside `frontend`. Vite forwards API calls and WebSocket updates to port 8000.

## Exact reference weights

`scripts/download_models.py` downloads pinned `v0.1.0` release assets from `yo-WASSUP/Good-Tennis` and `yo-WASSUP/Good-Badminton`. It validates file sizes and upstream digests when published, then records SHA-256 hashes and source URLs in `weights/manifest.json`.

| Purpose | Asset |
|---|---|
| Tennis object | `tennis-ball.pt` |
| Badminton object | `yolo11s-ball.pt` |
| YOLO pose | `yolo11s-pose.pt`, `yolo11n-pose.pt` |
| Person detector for RTMPose | `yolox_nano_8xb8-300e_humanart-40f6f0d0.onnx` |
| RTMPose | `rtmpose-s_simcc-body7_pt-body7_420e-256x192-acd4a1ef_20230504.onnx` |
| RTMO | `rtmo-s_8xb32-600e_body7-640x640-dac2bf74_20231211.onnx` |

YOLO adapters use the models' own inference preprocessing. RTMLib supplies the corresponding ONNX preprocessing and decoding with explicit local paths. There is no generic detector fallback or automatic model download during analysis. Inference adapters normalize detections to boxes, confidence and optional keypoints in image coordinates.

Reference tracking concepts studied: small-object area/aspect filtering, temporal prediction gates, bounded trajectory history and selectable pose families. The implementation here is independent. Third-party assets retain their upstream licenses; see [THIRD_PARTY.md](THIRD_PARTY.md).

## Architecture

```text
backend/app/
  main.py          Upload, stream, calibration, scoring and WebSocket API
  config.py        Runtime paths and environment configuration
  storage.py       SQLAlchemy session persistence
  queue.py         Local worker and Celery task entry point
  video.py         Bounded decode, overlapping chunks and activity gate
  models.py        Exact-weight YOLO / RTMPose / RTMO adapters
  court.py         Court suggestions and court-plane homography
  tracking.py      Persistent tracks, contact candidates and analytics
  sports.py        Abstract sport contract and singles rules
  pipeline.py      Ordered reduction, previews, records and MP4 export
backend/tests/     Rules, continuity, identity, API and retry checks
frontend/src/      React dashboard and responsive styling
scripts/           Download, start and real-model smoke test tools
weights/           Local models and provenance manifest
data/              Uploaded videos, database and session artifacts
```

`SportModule` isolates score formats and event interpretation. Register another subclass in `SPORTS`, add court dimensions, and supply its model entry to extend the engine. Modules share video ingestion, pose adapters, tracking and analytics.

### Chunking and activity filtering

Video is decoded into two-second chunks with half a second of overlap and a queue capacity of two. Frames retain source timestamps and indices; duplicate overlap frames are rejected before state updates. A half-second delayed buffer provides look-ahead for active-play pre-roll. Hysteresis preserves cooldown and a periodic probe prevents complete blindness during idle intervals. The original uploaded file is retained; dead-time filtering suppresses inference, not video frames.

Only reduced-resolution frame differences run during most idle periods. Camera movement and walking may trigger inference: this is a conservative compute gate, not a trained rally classifier. Benchmark missed rallies before making it more aggressive. Analytics do not interpolate across long detection gaps.

The prototype processes inference in order inside each session. Decode overlaps inference; Celery can distribute independent sessions. Stateless inference parallelism across chunks is intentionally not enabled because tracker state and GPU memory need explicit coordination. Full video chunks remain bounded in memory rather than accumulating in the broker.

### Scoring and confidence

Tennis supports deuce, advantage, games, best-of-three sets and a seven-point tiebreak at 6–6. Badminton supports 21-point rally scoring, win-by-two with a 30-point cap, and best-of-three games. These are fixed prototype formats, not a configurable tournament rules engine.

The rules engine can automatically score grounded, high-confidence observations supplied to `/observations`, including out-of-bounds landings and a second tennis bounce. The monocular detector currently generates **unverified image-space direction changes and hit candidates**. It cannot reliably establish ground contact; those observations remain in review. Therefore **unattended video-only automatic scoring is not validated or enabled**. Manual point confirmation is the normal dashboard workflow. Service faults, lets, net contacts and formal umpiring decisions are not inferred.

Repeated event IDs cannot add a second point. Corrections replay the point ledger. Score edits are restricted to sessions not currently processing to avoid competing snapshot writers.

### Measurement limits

- Object speed is **pixels per second at the analysis resolution**, not claimed as physical shot speed. Court homography cannot recover an airborne shuttle's 3D trajectory.
- Player distance and speed are court-plane estimates based on detected feet. Accurate court calibration and a fixed camera are required.
- Hits and rally durations are estimates from direction changes near player boxes. There is no racket-contact classifier. A three-second hit gap closes an estimated rally; this is not a scoring decision.
- Annotated export uses constant source FPS and does not retain audio. Variable-frame-rate sources may need normalization before precise playback comparison; original timestamps are preserved in JSONL.
- Heatmaps retain the latest 1,200 player positions and the dashboard retains up to 2,000 event candidates. Frame records contain all processed observations.
- Inference speed depends on hardware. A CPU may process more slowly than capture. The bounded queue prevents unlimited memory growth; live capture may buffer or drop frames upstream under load.

## Scalable deployment

With Docker Desktop using Linux containers or WSL2:

```sh
docker compose up --build
```

Download the model weights with `scripts/download_models.py` before starting Docker;
the containers mount the local `weights/` directory and do not download models.

This runs the API, one Celery worker, Redis and PostgreSQL. Shared data storage preserves media paths across API and worker containers. The supplied image is CPU-oriented. GPU deployment requires a compatible CUDA PyTorch build and ONNX Runtime GPU provider; provision that separately and benchmark before increasing worker concurrency.

Jobs use atomic state transitions so duplicate starts cannot claim the same session; overlap and event deduplication are implemented. A process crash can leave a session marked as processing; automatic crash recovery and resumable checkpoint replay are future work. Create a fresh session to rerun it. Avoid concurrent manual edits to the same session in this local prototype. Production deployment needs transactional score edits, authentication, upload retention limits and restricted camera destinations. The default server binds to localhost.

## Validation

The dashboard now includes a coach-focused **Tactical Report**, court-zone splits,
sprint bursts, rally pace and recovery summaries. See [Coaching reports](docs/COACHING.md)
for setup, measurement definitions and why flight speed remains unavailable without
validated flight measurements. Reanalyze older sessions to generate the new report.

```powershell
cd backend
../.venv/Scripts/python.exe -m pytest -q
cd ../frontend
npm run build
cd ..
.venv/Scripts/python.exe scripts/smoke_models.py
```

The optional smoke tool requires `Good-Tennis-main/videos/demo.mp4` and
`Good-Badminton-main/videos/demo.mp4` in sibling directories next to this repository.
These clips are not included in Git. It tests actual model loading and inference.
See `docs/VALIDATION.md` for historical outcomes. Docker and external live camera
testing depend on available host services.

The optional sports-CV endpoint is disabled by default. Enabling `SPORTS_CV_ENABLED`
also requires a separately provisioned `yolo26n-pose.pt` file or an explicit
`SPORTS_CV_WEIGHTS_PATH`; the seven-model download script does not supply that model.
See [sports-CV configuration](backend/app/sports_cv/README.md).
