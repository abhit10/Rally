"""Paired visual check of full-frame pose versus small-player rescue views.

This is a detection comparison, not an accuracy benchmark without human labels.
"""
import json
import argparse
import sys
from pathlib import Path
import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.models import YoloPoseAdapter, FILES
from app.config import WEIGHTS
from app.runtime import select_device
from app.player_detection import detect_players
from app.storage import recent
from app.court import PlayerCourtGuide


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',help='Local badminton video; defaults to the latest saved badminton match.')
    args=parser.parse_args()
    source=args.source or next(row for row in recent() if row['sport']=='badminton')['source']
    device=select_device('cuda','yolo-small')
    baseline=YoloPoseAdapter(WEIGHTS/FILES['yolo-small'],device,640)
    enhanced=YoloPoseAdapter(WEIGHTS/FILES['yolo-small'],device,960)
    capture=cv2.VideoCapture(source)
    panels=[]
    records=[]
    guide=PlayerCourtGuide('badminton')
    for second in (5,10,15,20,25,30):
        capture.set(cv2.CAP_PROP_POS_MSEC,second*1000)
        ok,frame=capture.read()
        if not ok:
            continue
        frame=cv2.resize(frame,(1280,round(frame.shape[0]*1280/frame.shape[1])))
        old_frame=cv2.resize(frame,(960,round(frame.shape[0]*.75)))
        old=baseline.detect(old_frame)
        court=guide.update(frame)
        new=detect_players(enhanced,frame,court)
        if court:
            new=[p for p in new if court.contains(court.project(p.foot),tolerance=.8)]
        pair=[]
        for label,people,scale in [('Before',old,4/3),('After',new,1)]:
            canvas=frame.copy()
            for person in people:
                x1,y1,x2,y2=[int(v*scale) for v in person.box]
                cv2.rectangle(canvas,(x1,y1),(x2,y2),(0,255,90),2)
                cv2.putText(canvas,f'{person.confidence:.2f}',(x1,max(30,y1-5)),cv2.FONT_HERSHEY_SIMPLEX,.6,(0,255,90),2)
            cv2.putText(canvas,f'{label} | {second}s',(15,30),cv2.FONT_HERSHEY_SIMPLEX,.8,(255,255,255),2)
            pair.append(cv2.resize(canvas,(640,round(canvas.shape[0]/2))))
        panels.append(np.hstack(pair))
        records.append({'time':second,'before':[{'box':[round(v*4/3,1) for v in p.box],'confidence':round(p.confidence,3)} for p in old],
                        'after':[{'box':[round(v,1) for v in p.box],'confidence':round(p.confidence,3)} for p in new]})
    capture.release()
    cv2.imwrite(str(ROOT/'docs/player-detection-comparison.jpg'),np.vstack(panels))
    (ROOT/'docs/player-detection-comparison.json').write_text(json.dumps(records,indent=2))
    print(json.dumps([{'time':r['time'],'before_count':len(r['before']),'after_count':len(r['after'])} for r in records]))


if __name__=='__main__':
    main()
