import numpy as np
from app.models import Detection
from app.player_detection import detect_players,far_court_views
from app.tracking import TrackingEngine
from app.court import Court,PlayerCourtGuide
from app.identity import PlayerIdentityTracker


def test_crop_coordinates_and_duplicate_suppression():
    class Pose:
        count=0
        def detect(self,image):
            self.count+=1
            if self.count==1:
                return [Detection([50,20,80,70],.7)]
            if self.count==2:
                return [Detection([50,20,80,70],.9,[[60,30,.8]])]
            return [Detection([30,20,50,60],.8,[[35,30,.8]])]
    people=detect_players(Pose(),np.zeros((200,200,3),np.uint8))
    assert len(people)==2
    assert people[0].confidence==.9
    assert people[1].box==[106,20,126,60]
    assert people[1].keypoints==[[111,30,.8]]


def test_partial_crop_person_is_not_created():
    class Pose:
        def detect(self,image):
            return [Detection([0,0,image.shape[1],image.shape[0]],.8)]
    assert len(detect_players(Pose(),np.zeros((200,200,3),np.uint8)))==1


def test_far_crop_contains_calibrated_baseline_and_net():
    court=Court('badminton',[[.3,.3],[.7,.3],[.9,.9],[.1,.9]],(1000,1000,3))
    left,top,right,bottom=far_court_views((1000,1000,3),court)[0]
    assert left<300 and right>700 and top<300 and bottom>450


def test_weak_but_consistent_far_player_can_get_identity():
    tracker=PlayerIdentityTracker(10)
    result=[]
    for _ in range(3):
        result=tracker.update([Detection([30,20,45,50],.28)],(200,200))
    assert len(result)==1
    assert result[0].track_id is not None


def test_new_identity_after_gap_reacquires_same_player():
    tracker=TrackingEngine()
    first=[Detection([20,10,40,40],.9,track_id=1),Detection([30,55,55,95],.9,track_id=2)]
    tracker.update([],first,0,(100,100,3))
    tracker.update([],[],.2,(100,100,3))
    result,_,_=tracker.update([],[Detection([21,10,41,40],.8,track_id=7),first[1]],.3,(100,100,3))
    assert set(result)=={'A','B'}
    assert result['B']['track_id']==7


def test_spectator_cannot_replace_player_inside_court():
    court=Court('badminton',[[.25,.1],[.75,.1],[.75,.9],[.25,.9]],(100,100,3))
    tracker=TrackingEngine()
    result,_,_=tracker.update([],[Detection([80,10,90,30],.99),Detection([40,10,50,30],.65),Detection([40,50,60,85],.8)],0,(100,100,3),court)
    assert set(result)=={'A','B'}
    assert result['B']['foot'][0]==45


def test_new_court_outline_releases_previously_selected_official():
    tracker=TrackingEngine()
    official=Detection([80,10,90,30],.99)
    near=Detection([40,50,60,85],.8)
    tracker.update([],[official,near],0,(100,100,3))
    court=Court('badminton',[[.25,.1],[.75,.1],[.75,.9],[.25,.9]],(100,100,3))
    result,_,_=tracker.update([],[official,near,Detection([40,10,50,30],.65)],.1,(100,100,3),court)
    assert set(result)=={'A','B'}
    assert result['B']['foot'][0]==45


def test_provisional_court_survives_occluded_lines_but_not_scene_cut(monkeypatch):
    corners=[[.2,.2],[.8,.2],[.9,.9],[.1,.9]]
    monkeypatch.setattr('app.court.suggest_court',lambda image:corners)
    guide=PlayerCourtGuide('badminton')
    original=guide.update(np.zeros((100,100,3),np.uint8))
    monkeypatch.setattr('app.court.suggest_court',lambda image:None)
    assert guide.update(np.full((100,100,3),5,np.uint8)) is original
    assert guide.update(np.full((100,100,3),255,np.uint8)) is None
