"""Delete only claimed, inactive sessions and exclusively owned uploaded media."""
from pathlib import Path
import re
import shutil
from .config import DATA
from .storage import get, save, transition, remove_claimed, source_references

DELETABLE = {'ready','completed','cancelled','failed','deletion_failed'}


def delete_session(session_id):
    if not re.fullmatch(r'[0-9a-f]{32}',session_id):
        raise ValueError('Invalid session identifier.')
    row = get(session_id)
    if row is None:
        return False
    if row['status'] not in DELETABLE:
        raise RuntimeError('Stop analysis and wait for completion before deleting this session.')
    root = (DATA/'sessions').resolve()
    folder = DATA/'sessions'/session_id
    # Check resolved absolute paths before any recursive operation.
    if folder.is_symlink() or folder.resolve().parent != root:
        raise ValueError('Session directory escapes managed storage.')
    if folder.exists():
        for child in folder.rglob('*'):
            if child.is_symlink() or not child.resolve().is_relative_to(folder.resolve()):
                raise ValueError('Session contains a link outside managed storage.')
    source = row.get('source')
    upload = None
    if not row.get('live') and isinstance(source,str):
        candidate = Path(source)
        upload_root = (DATA/'uploads').resolve()
        if candidate.is_absolute() and candidate.resolve().parent == upload_root and not candidate.is_symlink():
            if not source_references(source,session_id):
                upload = candidate
    row['status'] = 'deleting'
    if not transition(row,DELETABLE):
        raise RuntimeError('Session changed. Refresh before deleting.')
    try:
        if folder.exists():
            shutil.rmtree(folder)
        if upload:
            upload.unlink(missing_ok=True)
        remove_claimed(session_id)
    except OSError as exc:
        row.update(status='deletion_failed',error='Some files are in use. Close playback and retry deletion.')
        save(row)
        raise RuntimeError(row['error']) from exc
    return True
