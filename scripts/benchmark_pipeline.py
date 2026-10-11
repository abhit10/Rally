"""Measure actual pipeline wall time on a deterministic reference excerpt."""
import argparse
import json
from pathlib import Path
import sys
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
import cv2
from app.config import DATA
from app.storage import save, get
from app.main import new_session
from app.pipeline import run_session

parser = argparse.ArgumentParser()
parser.add_argument('--label', default='optimized')
parser.add_argument('--frames', type=int, default=90)
parser.add_argument('--stride', type=int, default=3)
parser.add_argument('--device', default='cuda')
args = parser.parse_args()
source = cv2.VideoCapture(str(ROOT.parent / 'Good-Badminton-main/videos/demo.mp4'))
fps = source.get(cv2.CAP_PROP_FPS)
source.set(cv2.CAP_PROP_POS_MSEC, 5000)
target = DATA / 'uploads' / (uuid4().hex + '.mp4')
writer = None
count = 0
for _ in range(args.frames):
    ok, image = source.read()
    if not ok:
        break
    if writer is None:
        writer = cv2.VideoWriter(str(target), cv2.VideoWriter_fourcc(*'mp4v'), fps, (image.shape[1], image.shape[0]))
    writer.write(image)
    count += 1
source.release()
writer.release()
row = new_session('badminton', 'yolo-small', str(target), f'Benchmark · {args.label}')
row.update(status='queued', options={'frame_stride':args.stride,'device':args.device,'inference_size':640,'max_width':960,'auto_score':False})
save(row)
started = time.perf_counter()
run_session(row['id'])
elapsed = time.perf_counter() - started
result = get(row['id'])
report = {'label':args.label,'frames':count,'seconds':round(elapsed,3),'fps':round(count/elapsed,2),'inferred_frames':result.get('inferred_frames'),'status':result['status'],'error':result.get('error'),'session_id':row['id'],'runtime':result.get('runtime')}
(ROOT / 'docs' / f'benchmark-{args.label}.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report),flush=True)
if result['status'] != 'completed':
    raise SystemExit(1)
