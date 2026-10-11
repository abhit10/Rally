"""Run actual inference on reference frames and a short end-to-end session per sport."""
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
import cv2
from app.models import ModelBundle
from app.main import new_session
from app.storage import save, get
from app.pipeline import run_session
from app.config import DATA

def main():
    report = []
    for sport, folder in [('tennis','Good-Tennis-main'), ('badminton','Good-Badminton-main')]:
        path = ROOT.parent / folder / 'videos' / 'demo.mp4'
        capture = cv2.VideoCapture(str(path))
        capture.set(cv2.CAP_PROP_POS_MSEC, 5000)
        ok, frame = capture.read()
        if not ok:
            raise RuntimeError(f'Cannot read {path}')
        frame = cv2.resize(frame, (640, round(frame.shape[0]*640/frame.shape[1])))
        bundle = ModelBundle(sport, 'yolo-nano')
        started = time.monotonic()
        objects, people = bundle.infer(frame)
        entry = {'sport':sport,'object_detections':len(objects),'players':len(people),'inference_seconds':round(time.monotonic()-started,3),'device':str(bundle.device)}
        clip = DATA / 'uploads' / f'smoke-{sport}.mp4'
        writer = cv2.VideoWriter(str(clip), cv2.VideoWriter_fourcc(*'mp4v'), 10, (frame.shape[1], frame.shape[0]))
        for _ in range(12):
            writer.write(frame)
            ok, next_frame = capture.read()
            if ok:
                frame = cv2.resize(next_frame, (frame.shape[1],frame.shape[0]))
        writer.release()
        capture.release()
        row = new_session(sport,'yolo-nano',str(clip),f'{sport.title()} · reference smoke test')
        row['status'] = 'queued'
        save(row)
        run_session(row['id'])
        completed = get(row['id'])
        entry.update(status=completed['status'], frames=completed.get('processed_frames'), error=completed.get('error'), session_id=row['id'])
        report.append(entry)
        print(json.dumps(entry),flush=True)
        if completed['status'] != 'completed':
            raise RuntimeError(completed.get('error'))
    output = ROOT / 'docs' / 'smoke-results.json'
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(report,indent=2),encoding='utf-8')

if __name__ == '__main__':
    main()
