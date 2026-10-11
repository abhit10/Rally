from fastapi.testclient import TestClient
from app.main import app, new_session
from app.storage import get
from app.storage import transition
import pytest

client = TestClient(app)


@pytest.mark.parametrize('profile,pose,stride',[('balanced','yolo-small',2),('fast','yolo-nano',3),('deep','rtmpose',1)])
def test_friendly_profile_configures_analysis(monkeypatch,profile,pose,stride):
    monkeypatch.setattr('app.main.check_weights',lambda *args:None)
    monkeypatch.setattr('app.main.select_device',lambda *args:0)
    monkeypatch.setattr('app.main.enqueue',lambda *args:None)
    row=new_session('badminton','yolo-small','unused','Profile test')
    result=client.post(f'/api/sessions/{row["id"]}/start',json={'profile':profile})
    assert result.status_code==200
    assert result.json()['pose']==pose
    assert result.json()['options']['frame_stride']==stride

def test_point_retries_and_undo_are_idempotent():
    row = new_session('tennis','yolo-small','unused','Test')
    path = f'/api/sessions/{row["id"]}/points'
    for _ in range(2):
        result = client.post(path,json={'winner':'A','event_id':'point-1'})
        assert result.status_code == 200
        assert result.json()['score']['points'] == ['15','0']
    assert client.delete(path+'/point-1').json()['score']['points'] == ['0','0']

def test_badminton_observations_never_award_points():
    row = new_session('badminton','yolo-small','unused','Test')
    path = f'/api/sessions/{row["id"]}/observations'
    client.post(path,json={'id':'hit','kind':'hit','time':0,'confidence':.99,'player':'A'})
    event = {'id':'landing','kind':'landing','time':1,'confidence':.99,'side':'B','inside':True,'grounded':True}
    assert client.post(path,json=event).json()['score']['points'] == ['0','0']
    assert client.post(path,json=event).json()['score']['points'] == ['0','0']

def test_unknown_media_and_invalid_upload():
    assert client.get('/api/sessions/not-found/media/source.jpg').status_code == 404
    assert client.post('/api/sessions/upload',data={'sport':'tennis'},files={'file':('fake.mp4',b'not-video','video/mp4')}).status_code == 400

def test_api_omits_stream_credentials():
    row = new_session('tennis','yolo-small','rtsp://user:password@camera/live','Live',True)
    response = client.get('/api/sessions/'+row['id'])
    assert 'source' not in response.json()

def test_uncertain_hitter_prevents_automatic_score():
    row = new_session('badminton','yolo-small','unused','Test')
    path = f'/api/sessions/{row["id"]}/observations'
    client.post(path,json={'id':'hit','kind':'hit','time':0,'confidence':.5,'player':'A'})
    result = client.post(path,json={'id':'landing','kind':'landing','time':1,'confidence':.99,'side':'B','inside':True,'grounded':True})
    assert result.json()['score']['points'] == ['0','0']

def test_only_one_worker_can_claim_a_session():
    row = new_session('tennis','yolo-small','unused','Test')
    row['status'] = 'queued'
    assert transition(row, ['ready'])
    assert not transition(row, ['ready'])
    row['status'] = 'loading'
    assert transition(row, ['queued'])
    assert not transition(row, ['queued'])


def test_badminton_manual_scoring_is_disabled():
    row=new_session('badminton','yolo-small','unused','Coaching')
    path=f'/api/sessions/{row["id"]}/points'
    assert client.post(path,json={'winner':'A','event_id':'one'}).status_code==409
    assert client.delete(path+'/one').status_code==409
    assert not client.get('/api/sessions/'+row['id']).json()['scoring_enabled']
