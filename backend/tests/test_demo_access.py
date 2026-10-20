from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient
from app.demo_access import DemoAccess
import pytest
from starlette.websockets import WebSocketDisconnect

def test_demo_key_guards_requests_and_live_sources(monkeypatch):
    monkeypatch.setenv('RALLY_DEMO_KEY', 'test-key')
    app = FastAPI()
    app.add_middleware(DemoAccess)
    @app.get('/api/health')
    def health(): return {'status': 'ok'}
    @app.websocket('/ws')
    async def ws(socket: WebSocket):
        await socket.accept()
        await socket.send_text('ok')
    client = TestClient(app)
    assert client.get('/api/health').status_code == 401
    assert client.get('/api/health?demo_key=wrong').status_code == 401
    assert client.get('/api/health?demo_key=test-key').status_code == 200
    assert client.post('/api/sessions/live?demo_key=test-key').status_code == 403
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect('/ws'): pass
    with client.websocket_connect('/ws?demo_key=test-key') as socket:
        assert socket.receive_text() == 'ok'
    monkeypatch.delenv('RALLY_DEMO_KEY')
    assert client.get('/api/health').status_code == 200
