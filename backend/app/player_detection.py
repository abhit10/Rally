"""Additional small-player views using the same sport-reference pose weights."""
import math
import cv2
import numpy as np
from .models import Detection


def far_court_views(shape, court=None):
    height, width = shape[:2]
    if court is not None:
        ground = np.array([[[0,0],[court.width,0],[court.width,court.length/2],[0,court.length/2]]],np.float32)
        points = cv2.perspectiveTransform(ground,np.linalg.inv(court.transform))[0]
        if np.isfinite(points).all():
            left, top = points.min(axis=0)
            right, bottom = points.max(axis=0)
            # Include players' heads above the baseline and lateral lunges.
            pad_x = max(24,(right-left)*.15)
            pad_y = max(40,(bottom-top)*.55)
            return [(max(0,int(left-pad_x)),max(0,int(top-pad_y)),
                     min(width,int(right+pad_x)),min(height,int(bottom+pad_y*.15)))]
    # With no court outline, overlapping views cover the entire upper court.
    return [(0,0,int(width*.62),int(height*.68)),
            (int(width*.38),0,width,int(height*.68))]


def overlap(a,b):
    intersection=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
    area_a=max(0,a[2]-a[0])*max(0,a[3]-a[1])
    area_b=max(0,b[2]-b[0])*max(0,b[3]-b[1])
    return intersection/max(area_a+area_b-intersection,1)


def detect_players(adapter, frame, court=None):
    candidates=list(adapter.detect(frame))
    for left,top,right,bottom in far_court_views(frame.shape,court):
        if right-left < 32 or bottom-top < 32:
            continue
        for person in adapter.detect(frame[top:bottom,left:right]):
            x1,y1,x2,y2=person.box
            # Exclude a person cut at an internal tile edge; the overlapping view
            # or full image sees their complete body instead.
            if (left>0 and x1<3) or (right<frame.shape[1] and x2>right-left-3) or (bottom<frame.shape[0] and y2>bottom-top-3):
                continue
            points=[[p[0]+left,p[1]+top,*p[2:]] if len(p)>=2 and (len(p)<3 or p[2]>0) else list(p) for p in person.keypoints]
            candidates.append(Detection([x1+left,y1+top,x2+left,y2+top],person.confidence,points))
    kept=[]
    for person in sorted(candidates,key=lambda p:p.confidence,reverse=True):
        if not all(math.isfinite(v) for v in person.box) or person.confidence < .15:
            continue
        if any(overlap(person.box,other.box)>.45 for other in kept):
            continue
        kept.append(person)
    return kept
