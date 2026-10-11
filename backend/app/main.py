"""Local prototype API. Deploy behind authentication before exposing remotely."""
import asyncio
import json
import re
from pathlib import Path
from typing import Literal
from uuid import uuid4
import cv2
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from .config import DATA, ROOT
from .models import check_weights, inventory
from .court import validate_corners, suggest_court
from .sports import score_session, SPORTS, RallyEvent
from .storage import save, get, recent, transition, ConcurrentUpdate
from .runtime import runtime_status, select_device
from .session_management import delete_session
from .queue import enqueue

app = FastAPI(title='Rally / Racket Intelligence', version='0.1.0')
Sport = Literal['tennis', 'badminton']
Pose = Literal['yolo-small', 'yolo-nano', 'rtmpose', 'rtmo']
BUSY = {'queued', 'loading', 'processing', 'encoding', 'deleting', 'deletion_failed'}

@app.exception_handler(ConcurrentUpdate)
async def conflict_handler(request, exc):
    return JSONResponse(status_code=409, content={'detail':str(exc)})

def lookup(session_id):
    row = get(session_id)
    if not row:
        raise HTTPException(404, 'Session not found.')
    return row

def public(row):
    result = {key: value for key, value in row.items() if key != 'source'}
    result['scoring_enabled'] = row['sport'] != 'badminton'
    if row['sport']=='badminton':
        result['score'] = score_session({'sport':'badminton','events':[]})
    return result

def new_session(sport, pose, source, name, live=False):
    session = {'id': uuid4().hex, 'sport': sport, 'pose': pose, 'source': source, 'name': name, 'live': live, 'status': 'ready', 'events': [], 'corners': None, 'analytics': {}, 'processed_frames': 0, 'inferred_frames': 0}
    session['score'] = score_session(session)
    save(session)
    return session

@app.get('/api/health')
def health():
    return {'status': 'ok', 'models': inventory(), 'runtime':runtime_status()}

@app.get('/api/sessions')
def sessions():
    return [public(row) for row in recent()]

@app.post('/api/sessions/upload')
async def upload(sport: Sport = Form(...), pose: Pose = Form('yolo-small'), file: UploadFile = File(...)):
    suffix = Path(file.filename or '').suffix.lower()
    if suffix not in {'.mp4', '.mov', '.avi', '.mkv', '.webm'}:
        raise HTTPException(400, 'Choose an MP4, MOV, AVI, MKV or WebM video.')
    path = DATA / 'uploads' / (uuid4().hex + suffix)
    total = 0
    try:
        with path.open('wb') as output:
            while block := await file.read(1024 * 1024):
                total += len(block)
                if total > 4 * 1024**3:
                    raise HTTPException(413, 'Maximum upload size is 4 GB.')
                output.write(block)
        capture = cv2.VideoCapture(str(path))
        ok, frame = capture.read()
        capture.release()
        if not ok:
            raise HTTPException(400, 'The uploaded file has no decodable video.')
        row = new_session(sport, pose, str(path), Path(file.filename).name)
        folder = DATA / 'sessions' / row['id']
        folder.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(folder / 'source.jpg'), frame)
        row.update(source_image=f'/api/sessions/{row["id"]}/media/source.jpg', suggested_corners=suggest_court(frame))
        save(row)
        return public(row)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    finally:
        await file.close()

class LiveRequest(BaseModel):
    sport: Sport
    pose: Pose = 'yolo-small'
    source: str = Field(min_length=1, max_length=2000)

@app.post('/api/sessions/live')
def live(request: LiveRequest):
    if request.source != 'camera:0' and not request.source.startswith(('rtsp://', 'http://', 'https://')):
        raise HTTPException(400, 'Use camera:0 or an RTSP/HTTP video stream URL.')
    return public(new_session(request.sport, request.pose, 0 if request.source == 'camera:0' else request.source, 'Live camera', True))

@app.get('/api/sessions/{session_id}')
def session(session_id: str):
    return public(lookup(session_id))

class Calibration(BaseModel):
    profile: Literal["balanced","fast","deep"] | None = None
    corners: list[list[float]] | None = None
    frame_stride: Literal[1,2,3] = 3
    inference_size: Literal[512,640,960] = 640
    max_width: Literal[640,960,1280] = 1280
    device: Literal['cuda','cpu','auto'] = 'auto'
    auto_score: bool = False
    score_threshold: float = Field(default=.75, ge=.6, le=.99)

@app.post('/api/sessions/{session_id}/start')
def start(session_id: str, request: Calibration):
    row = lookup(session_id)
    if row['status'] not in {'ready', 'failed'}:
        raise HTTPException(409, 'This session has already been started. Upload again for a new analysis.')
    try:
        if request.profile:
            row['pose'], request.frame_stride = {'balanced':('yolo-small',2),'fast':('yolo-nano',3),'deep':('rtmpose',1)}[request.profile]
        check_weights(row['sport'], row['pose'])
        row['corners'] = validate_corners(request.corners) if request.corners else None
        select_device(request.device,row['pose'])
        row['options'] = request.model_dump(exclude={'corners'})
        row['options']['auto_score'] = False
    except (ValueError, FileNotFoundError, RuntimeError) as exc:
        raise HTTPException(422, str(exc)) from exc
    row['status'] = 'queued'
    row['error'] = None
    (DATA / 'sessions' / session_id / 'stop').unlink(missing_ok=True)
    if not transition(row, ['ready', 'failed']):
        raise HTTPException(409, 'Another request already started this session.')
    try:
        enqueue(session_id)
    except Exception as exc:
        row.update(status='failed', error='Could not reach the processing queue.')
        save(row)
        raise HTTPException(503, row['error']) from exc
    return public(row)

@app.post('/api/sessions/{session_id}/stop')
def stop(session_id: str):
    row = lookup(session_id)
    if row['status'] not in {'queued','loading','processing','encoding'}:
        return {'requested':False}
    folder = DATA / 'sessions' / session_id
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'stop').touch()
    return {'requested': row['status'] in BUSY}

@app.delete('/api/sessions/{session_id}')
def delete(session_id: str):
    try:
        removed = delete_session(session_id)
        return {'deleted':removed, 'id':session_id}
    except ValueError as exc:
        raise HTTPException(400,str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(409,str(exc)) from exc

class PointRequest(BaseModel):
    winner: Literal['A', 'B']
    event_id: str = Field(min_length=1, max_length=100)

def editable(row):
    if row['status'] in BUSY:
        raise HTTPException(409, 'Pause until processing finishes before correcting the score.')

@app.post('/api/sessions/{session_id}/points')
def point(session_id: str, request: PointRequest):
    row = lookup(session_id)
    editable(row)
    if row['sport']=='badminton':
        raise HTTPException(409,'Badminton sessions focus on coaching. Point counting is disabled.')
    found = next((event for event in row['events'] if event['id'] == request.event_id), None)
    if found:
        found.update(winner=request.winner, status='confirmed', reviewed=True)
    else:
        row['events'].append({'id': request.event_id, 'kind': 'manual point', 'time': row.get('source_seconds', 0), 'winner': request.winner, 'status': 'confirmed', 'reviewed': True})
    row['score'] = score_session(row)
    save(row)
    return public(row)

@app.delete('/api/sessions/{session_id}/points/{event_id}')
def undo(session_id: str, event_id: str):
    row = lookup(session_id)
    editable(row)
    if row['sport']=='badminton':
        raise HTTPException(409,'Badminton sessions focus on coaching. Point counting is disabled.')
    for event in row['events']:
        if event['id'] == event_id:
            event['status'] = 'dismissed'
    row['score'] = score_session(row)
    save(row)
    return public(row)

class Observation(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    kind: Literal['hit', 'bounce', 'landing']
    time: float = Field(ge=0)
    confidence: float = Field(ge=0, le=1)
    player: Literal['A', 'B'] | None = None
    side: Literal['A', 'B'] | None = None
    inside: bool | None = None
    grounded: bool = False

@app.post('/api/sessions/{session_id}/observations')
def observation(session_id: str, request: Observation):
    row = lookup(session_id)
    editable(row)
    if any(event['id'] == request.id for event in row['events']):
        return public(row)
    event = request.model_dump()
    event['status'] = 'review'
    row['events'].append(event)
    module = SPORTS[row['sport']]()
    for item in sorted(row['events'], key=lambda x: x['time']):
        if item['kind'] not in ('hit', 'bounce', 'landing') or item.get('status') == 'dismissed':
            continue
        winner = module.interpret(RallyEvent(**{key: item[key] for key in RallyEvent.__dataclass_fields__ if key in item}))
        if row['sport']!='badminton' and item['id'] == request.id and winner and module.decision_confidence >= 0.9:
            item.update(winner=winner, status='confirmed')
    row['score'] = score_session(row)
    save(row)
    return public(row)

@app.get('/api/sessions/{session_id}/media/{filename}')
def media(session_id: str, filename: str):
    lookup(session_id)
    if filename not in {'source.jpg', 'preview.jpg', 'annotated.mp4', 'frames.jsonl'} and not re.fullmatch(r'preview-\d+\.jpg',filename):
        raise HTTPException(404)
    path = DATA / 'sessions' / session_id / filename
    if not path.is_file():
        raise HTTPException(404)
    if filename.endswith('.jpg'):
        try:
            return Response(path.read_bytes(),media_type='image/jpeg',headers={'Cache-Control':'no-store'})
        except (FileNotFoundError, PermissionError):
            raise HTTPException(404,'Preview refreshed; use the newest frame.')
    return FileResponse(path, headers={'Cache-Control': 'no-store'} if filename.endswith('.jpg') else {})

@app.websocket('/api/sessions/{session_id}/ws')
async def updates(websocket: WebSocket, session_id: str):
    await websocket.accept()
    try:
        previous = None
        while True:
            row = await asyncio.to_thread(get, session_id)
            if not row:
                await websocket.close(code=1008)
                return
            if row['updated_at'] != previous:
                await websocket.send_json(public(row))
                previous = row['updated_at']
            await asyncio.sleep(0.7)
    except (WebSocketDisconnect, RuntimeError):
        return

frontend = ROOT / 'frontend' / 'dist'
if frontend.is_dir():
    app.mount('/', StaticFiles(directory=frontend, html=True), name='dashboard')

from .sports_cv.router import router as sports_cv_router
from .sports_cv.config import SPORTS_CV_ENABLED

if SPORTS_CV_ENABLED:
    app.include_router(sports_cv_router)

