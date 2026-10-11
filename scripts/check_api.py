"""Check upload, asynchronous processing and media delivery through the running API."""
from pathlib import Path
import time
import httpx

ROOT = Path(__file__).resolve().parents[1]
with httpx.Client(base_url='http://127.0.0.1:8000', timeout=30) as client:
    assert client.get('/api/health').status_code == 200
    with (ROOT / 'data/uploads/smoke-tennis.mp4').open('rb') as video:
        response = client.post('/api/sessions/upload', data={'sport':'tennis','pose':'yolo-nano'}, files={'file':('API validation.mp4',video,'video/mp4')})
    response.raise_for_status()
    session = response.json()
    path = '/api/sessions/' + session['id']
    response = client.post(path+'/start', json={'corners':None})
    response.raise_for_status()
    assert client.post(path+'/start', json={'corners':None}).status_code == 409
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        session = client.get(path).json()
        if session['status'] in ('completed','failed'):
            break
        time.sleep(.5)
    assert session['status'] == 'completed', session
    media = client.get(session['video'], headers={'Range':'bytes=0-99'})
    assert media.status_code == 206
    print({'session':session['id'],'status':session['status'],'frames':session['processed_frames'],'media_range_status':media.status_code}, flush=True)
