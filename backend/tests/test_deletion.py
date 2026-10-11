from pathlib import Path
import pytest
from app.config import DATA
from app.main import new_session
from app.storage import get,save,ConcurrentUpdate
from app.session_management import delete_session

def prepare_session():
    row=new_session('tennis','yolo-small','unused','Deletion test')
    folder=DATA/'sessions'/row['id']
    folder.mkdir(parents=True)
    (folder/'stats.json').write_text('{}')
    upload=DATA/'uploads'/(row['id']+'.mp4')
    upload.write_bytes(b'test video')
    row.update(source=str(upload),status='completed')
    save(row)
    return row,folder,upload

def test_deletes_owned_files_and_database_idempotently():
    row,folder,upload=prepare_session()
    stale=get(row['id'])
    assert delete_session(row['id'])
    assert not folder.exists() and not upload.exists() and get(row['id']) is None
    assert not delete_session(row['id'])
    with pytest.raises(ConcurrentUpdate):
        save(stale)

def test_busy_session_cannot_be_deleted():
    row,folder,upload=prepare_session()
    row['status']='processing'
    save(row)
    with pytest.raises(RuntimeError):
        delete_session(row['id'])
    assert folder.exists() and upload.exists()

def test_source_outside_uploads_is_preserved(tmp_path):
    row,folder,_=prepare_session()
    original=tmp_path/'original.mp4'
    original.write_bytes(b'keep')
    row['source']=str(original)
    save(row)
    delete_session(row['id'])
    assert original.read_bytes() == b'keep'

def test_shared_upload_is_preserved():
    row,_,upload=prepare_session()
    other=new_session('tennis','yolo-small',str(upload),'Shared source')
    delete_session(row['id'])
    assert upload.exists() and get(other['id'])

def test_path_traversal_is_rejected():
    with pytest.raises(ValueError):
        delete_session('../uploads')
