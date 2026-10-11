# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Two confirmed audiences, both reviewing racket-sport singles footage shot on a single
fixed camera with the whole court in view:

- **Coaches** reviewing a student's recorded match to find positioning, rally and
  workload patterns worth working on in the next practice session.
- **Self-coaching club players** reviewing their own matches with no coach present to
  interpret the numbers for them.

Both read the same workspace. Nothing may assume a trained analyst is reading it, and
nothing may assume a coach is standing by to correct a misleading figure.

## Product Purpose

Rally turns one ordinary video of a tennis or badminton singles match into reviewable
intelligence: court movement and distance, net-versus-rear-court positioning, sprint
bursts, rally durations and pace, work-to-rest context, and a tactical report built for
coach-led review. Tennis sessions also keep a manually confirmed point ledger.

Success is a reviewer who finishes a session knowing something actionable about the
play, and who trusts every number they were shown.

## Positioning

**Honest measurement.** Rally's differentiator is what it refuses to claim. A monocular
fixed camera cannot recover an airborne ball's 3D flight, cannot reliably establish
ground contact, and cannot grade technique — so Rally reports those as unavailable
rather than estimating them. Competing tools present confident numbers for things their
pipeline cannot actually measure; Rally's credibility is the thing a neighbouring product
could not truthfully copy without rebuilding its measurement discipline.

This is a product claim with teeth: measurement limits are documented per metric
(`docs/COACHING.md`), speeds are labelled in their real units (pixels per second at
analysis resolution, not shot speed), and validated-3D shot speed exists as an
extension point rather than a shipped figure.

## Operating Context

1. The reviewer picks Tennis or Badminton and uploads a match video (MP4, MOV, AVI, MKV,
   WebM) or connects an RTSP / IP-camera feed or the server's webcam.
2. They mark the four **singles** court corners in order — far-left, far-right,
   near-right, near-left — on a still frame. Automatic suggestions may appear and are
   inspected before use. Calibration is what unlocks all physical movement metrics.
3. They choose an analysis profile (Fast Mode, Balanced, Deep Analysis) and start
   analysis. Processed frames, estimated hits, activity filtering and event candidates
   arrive live over a WebSocket.
4. They play the completed annotated video, review contact candidates, and — in tennis —
   confirm points to A or B, with corrections and undo.
5. They export the annotated MP4 or the frame-level JSONL observations, and read the
   Tactical Report for zone splits, sprint bursts, rally pace and recovery.

Player A starts on the near side, Player B on the far side. Long occlusions or a change
of ends can require a new session. The camera must stay still; camera movement
invalidates the calibration.

Runs locally by default (SQLite, one session worker, no Redis or Docker required) and
binds to localhost. A Docker Compose path adds Celery, Redis and PostgreSQL for
multi-session throughput.

## Capabilities and Constraints

**Confirmed capabilities**

- Shared vision engine across tennis and badminton via a `SportModule` contract; new
  sports register a subclass, court dimensions and a model entry.
- Pinned local reference weights (YOLO object and pose, RTMPose, RTMO, YOLOX person
  detector) with SHA-256 provenance in `weights/manifest.json`. No automatic model
  download during analysis, and no generic detector fallback.
- Two-second decode chunks with half-second overlap, a bounded queue, duplicate-frame
  rejection and a conservative frame-difference activity gate that suppresses inference,
  never video frames.
- Court-plane homography for foot-position distance and speed; persistent identity
  association that can reacquire a nearby player after a short loss.
- Tennis rules: deuce, advantage, games, best-of-three sets, seven-point tiebreak at 6–6.
  Badminton rules: 21-point rally scoring, win-by-two, 30-point cap, best of three.
  Both are fixed prototype formats, not a configurable tournament engine.
- Tactical Report on version 2 analytics: zone splits, sprints, high-intensity share,
  rally distribution, work-to-rest, rally pace, review moments with video links.

**Binding constraints**

- **Singles boundaries and a fixed camera.** Court geometry assumes singles sidelines,
  not doubles, and a stationary camera with the full court visible. Doubles and moving
  cameras are out of scope.
- **Missing measurements render as a dash, never as zero and never as an invented
  value.** This holds for every surface, every metric, every state.
- Calibration gates physical metrics: no confirmed corners means no distance, no speed,
  no zone split. Live streams currently run without interactive calibration, so their
  movement metrics stay unavailable unless corners arrive through the API.

**Implemented behaviour (factual, recorded so future work does not contradict it)**

- Badminton sessions do not award points. Manual point entry and undo reject badminton
  requests; the dashboard shows a coaching notebook in place of a scoreboard.
- Unattended video-only automatic scoring is not validated or enabled. The detector
  produces unverified image-space direction changes and hit candidates, which stay in
  review. Manual point confirmation is the normal tennis workflow.
- Service faults, lets, net contacts and formal umpiring decisions are not inferred.
- Score edits are blocked while a session is processing. A crashed process can leave a
  session marked as processing; crash recovery and resumable checkpoints are future work.
- Retention caps: 1,200 most recent player positions per heatmap, up to 2,000 event
  candidates in the dashboard. Frame records keep every processed observation.
- **Undecided:** authentication, upload retention limits, transactional score edits,
  restricted camera destinations and GPU deployment are explicitly not solved. Do not
  design UI that implies they exist.

**Terminology**

Session · rally · hit / contact candidate · event candidate · court calibration
(corners) · zone split (net play vs rear court) · sprint burst · work-to-rest ratio ·
rally pace · analysis profile (Fast Mode / Balanced / Deep Analysis) · Tactical Report ·
observations (JSONL) · Player A (near court) / Player B (far court).

## Brand Commitments

- Name: **Rally**, in the product's own wordmark as lowercase `rally.`; the workspace
  identity is "Racket Intelligence".
- Stack as built: React 19 + Vite + TypeScript, hand-written CSS with custom properties,
  `lucide-react` icons. FastAPI backend behind `/api`.
- Voice as written: plain, calm, second-person, coach-adjacent. It states limits in the
  same tone it states findings, and it does not hype the technology.

## Evidence on Hand

- `README.md` — architecture, chunking and activity filtering, scoring formats, and an
  explicit measurement-limits section.
- `docs/COACHING.md` — per-metric measurement definitions, and the reasoning for why
  flight speed stays unavailable.
- `docs/COACHING-VALIDATION.md`, `docs/VALIDATION.md` — recorded validation outcomes.
- `docs/benchmark-before.json`, `docs/benchmark-optimized.json` — real pipeline benchmarks.
- `docs/smoke-results.json` plus `scripts/smoke_models.py` — real model load and inference
  on short local clips.
- `docs/player-detection-comparison.jpg` / `.json`, `scripts/check_player_recall.py` —
  paired before/after detection contact sheets. Detection counts are not accuracy
  measurements without human labels.
- `docs/dashboard.png`, `docs/coaching-report.png` — captures of the shipped dashboard.
- `backend/tests/` — rules, continuity, identity, coaching-metric, player-detection, API
  and retry coverage.
- `weights/manifest.json` — model provenance with hashes and source URLs.
- `THIRD_PARTY.md` — upstream licenses.

**Absences future work must not fabricate:** there are no customers, testimonials, case
studies, press mentions, usage numbers, accuracy percentages, pricing or deployment
claims. There is no validated shot-speed figure. There are no human-labelled accuracy
benchmarks.

## Product Principles

1. **Never invent a number.** An unavailable measurement is a dash. A pixel-space value
   is labelled as pixel-space. An estimate is called an estimate. Showing less is always
   preferable to showing something unearned.
2. **Name the limit beside the finding.** Every metric carries its conditions — what
   calibration it needed, what it excludes, what it does not prove. The limit is part of
   the insight, not a disclaimer hidden elsewhere.
3. **The human stays the judge.** The engine proposes candidates; the reviewer confirms
   outcomes and interprets patterns. No surface may imply autonomous umpiring or
   automatic technique grading.
4. **Readable without an analyst.** A self-coaching club player and a coach see the same
   workspace, so every figure must be interpretable by someone with no analytics
   background and no one to ask.
5. **One camera is the whole premise.** Design for a single fixed view, imperfect
   detections, occlusions and gaps — not for an instrumented court.
