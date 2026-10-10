# CourtTrace

Single-camera racket-sports analysis for a four-person, 24-hour hackathon.

**Current state:** a local FastAPI review app on top of an English vision foundation. Upload a singles recording, run automatic court detection, review player tracks, confirm point winners, inspect evidence-linked movement insights, and keep player history in SQLite.

**Product chain:** video -> automatic court setup -> player movement -> reviewed rallies and scoring -> evidence-linked insights -> persistent player history.

## Quick start

Use Python 3.12.

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m courttrace.app
```

Then open http://127.0.0.1:8000

Optional player tracking (frozen YOLO Pose; no team training):

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-models.txt
```

Court calibration still runs without Ultralytics. Processing a match for player tracks requires the model extra; if it is missing, the job fails with an install message instead of inventing tracks.

macOS/Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m courttrace.app
```

Headless calibration only:

```powershell
.\.venv\Scripts\python.exe -m courttrace.calibrate --video samples\match.mp4 --output outputs\match --samples 3
```

Place a permitted local video at `samples/match.mp4`, or upload through the web UI. Videos and model weights are not included. See [sample guidance](samples/README.md).

Application data stays in the ignored `var/` directory (SQLite, uploads, per-match JSONL). Calibration CLI outputs stay in `outputs/`.

API example against a running server:

```powershell
.\.venv\Scripts\python.exe examples\api_example.py
```

## What works and what remains

| Component | Status |
| --- | --- |
| Automatic court candidates from video | Implemented; badminton smoke-tested on a short starter clip |
| Court coordinate mapping and JSON export | Implemented and unit-tested |
| Tennis geometry and tie-break ruleset | Implemented in the shared engine; footage accuracy not established |
| Optional YOLO pose/shuttle adapters | Pose used in processing when Ultralytics is installed; shuttle off the default path |
| Two player tracks with visible gaps | Implemented; spectators filtered by court geometry |
| Rally review and confirmed scoring | Implemented (suggestions heuristic; winners are user-confirmed) |
| Evidence-linked insights and player history | Implemented; withheld without candidate calibration |
| Web UI and backend application | Implemented (FastAPI + local HTML) |
| Automatic point-winner recognition | Not implemented; do not claim it |

The detector currently inherits assumptions about elevated rear views; badminton also uses green-court colour cues. The starter overlay can show line offsets. **A returned `candidate` is not a verified calibration or an accuracy claim.**

Statuses: `candidate` means provisional support and multi-frame consistency gates passed; `needs_review` or `failed` withholds the final transform. Exit codes for the calibration CLI are 0, 2, and 1 for candidate, insufficient calibration, and input/runtime error respectively.

## Rulesets

- `badminton_singles_21`: BWF rally point, 21, win by 2, cap 30.
- `tennis_tiebreak_7`: tie-break to 7, win by 2 (short transfer clips).

Score is replayed only from confirmed point-winner events.

## Repository layout

```text
courttrace/
  app.py                 FastAPI + static review UI
  calibrate.py           Automatic video-calibration entry point
  pipeline.py            Match processing job
  store.py               SQLite persistence
  scoring.py             Ruleset replay
  insights.py            Occupancy and path metrics
  court/                 Detector, sport references, coordinate mapper
  detection/             Optional pretrained model adapters
  tracking/              Footpoints, halves, rally suggestions
  sports/                Geometry, zones, ruleset identifiers
  web/                   Local HTML/JS review app
  data/                  Structured JSON/JSONL writers
tests/
docs/
examples/api_example.py
```

## Optional models

`requirements-models.txt` adds Ultralytics. Install it only when needed. Weights are not included, and dependency/model licences are separate from this repository's source licence.

## Verification

Foundation and application tests: `python -m unittest discover -s tests -v`. GitHub Actions is configured for Python 3.12 on Windows and Linux. No accuracy, new-venue generalisation, or full-match analysis benchmark has been established. Tennis support is a real second configuration, not a renamed badminton court; it is untested on tennis footage until a transfer clip is processed.

## Attribution

Selected vision components derive from [Good-Badminton](https://github.com/yo-WASSUP/Good-Badminton), Copyright 2026 Good-Badminton contributors, under Apache-2.0. Attribution, the original licence, modifications, and source hashes are retained. The original Chinese reference archive is not bundled. Maintained documentation, logs, and source text are English; text within input footage is unchanged.
