import cv2
import numpy as np
import pytest
from app.video import VideoSource, ActivityGate, Frame
from app.court import Court, validate_corners
from app.tracking import TrackingEngine
from app.models import Detection

def create_video(path, count=73):
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'mp4v'), 20, (160, 120))
    for index in range(count):
        image = np.zeros((120, 160, 3), np.uint8)
        cv2.circle(image, (20 + index, 50), 5, (255,255,255), -1)
        writer.write(image)
    writer.release()

def test_overlapping_chunks_preserve_all_frames(tmp_path):
    path = tmp_path/'clip.mp4'
    create_video(path)
    chunks = list(VideoSource(str(path), chunk_seconds=1, overlap_seconds=.25))
    unique = {frame.index: frame.time for chunk in chunks for frame in chunk.frames}
    assert sorted(unique) == list(range(73))
    assert sum(len(chunk.frames) for chunk in chunks) > 73
    assert all(unique[i+1] > unique[i] for i in range(72))

def test_idle_gate_probes_and_motion_reopens():
    gate = ActivityGate()
    still = np.zeros((120,160,3), np.uint8)
    assert gate.inspect(Frame(0, 0, still))[0]
    assert not gate.inspect(Frame(1, 1.8, still))[0]
    assert gate.inspect(Frame(2, 2.1, still))[0]
    assert gate.inspect(Frame(3, 2.2, np.full_like(still, 255)))[0]

def test_court_mapping_and_invalid_corners():
    corners = [[.1,.1],[.9,.1],[.9,.9],[.1,.9]]
    court = Court('tennis', corners, (100,100,3))
    assert np.allclose(court.project((50,50)), [4.115,11.885])
    with pytest.raises(ValueError):
        validate_corners([[0,0],[1,1],[1,0],[0,1]])

def test_track_gap_does_not_invent_speed():
    tracker = TrackingEngine()
    ball = Detection([10,10,14,14], .95)
    tracker.update([ball],[],0,(100,100,3))
    tracker.update([],[],1,(100,100,3))
    tracker.update([Detection([70,70,74,74],.95)],[],2,(100,100,3))
    assert tracker.object_speed is None

def test_player_ids_survive_detector_order_changes():
    tracker = TrackingEngine()
    near = Detection([30,55,55,95],.9)
    far = Detection([30,5,55,45],.9)
    first,_,_ = tracker.update([], [near,far],0,(100,100,3))
    second,_,_ = tracker.update([], [far,near],.1,(100,100,3))
    assert first['A']['foot'] == second['A']['foot']
    assert first['B']['foot'] == second['B']['foot']
