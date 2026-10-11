import numpy as np
import pytest
from app.rally import RallyMachine, RallyState, ContactDetector
from app.sports import RallyEvent
from app.court import Court
from app.models import Detection
from app.interpolation import interpolate_tracks

def event(kind,time,**kwargs):
    return RallyEvent(kind,time,.95,**kwargs)

def test_tennis_second_bounce_scores_exactly_once():
    machine=RallyMachine('tennis')
    machine.step([event('hit',0,player='A')],0)
    assert machine.state == RallyState.IN_RALLY
    machine.observe_ball(.4)
    machine.step([event('bounce',.4,side='B',inside=True,grounded=True)],.4)
    bounce=event('bounce',.8,side='B',inside=False,grounded=True)
    machine.observe_ball(.8)
    machine.step([bounce],.8)
    assert machine.state == RallyState.RALLY_ENDED
    decision=machine.step([bounce],.9)
    assert machine.state == RallyState.UPDATE_SCORE
    assert decision.winner == 'A' and decision.status == 'confirmed'
    assert machine.step([bounce],1.0) is None
    machine.step([],2.0)
    assert machine.state == RallyState.WAITING_FOR_SERVE

def test_lost_ball_never_ends_with_a_point():
    machine=RallyMachine('badminton')
    machine.step([event('hit',0,player='A')],0)
    assert machine.step([],2) is None
    assert machine.state == RallyState.WAITING_FOR_SERVE
    assert machine.step([event('landing',2.1,side='B',inside=True,grounded=True)],2.1) is None

def test_airborne_outside_and_line_uncertainty_do_not_score():
    machine=RallyMachine('tennis')
    machine.step([event('hit',0,player='A')],0)
    machine.step([event('bounce',.1,side='B',inside=False,grounded=False)],.1)
    machine.step([event('bounce',.2,side='B',inside=None,grounded=True)],.2)
    assert machine.state == RallyState.IN_RALLY

def test_badminton_ground_contact_from_observed_trajectory_updates_score():
    court=Court('badminton',[[.1,.1],[.9,.1],[.9,.9],[.1,.9]],(1000,1000,3))
    players={'A':{'box':[400,650,500,850],'foot':[450,850]},'B':{'box':[400,150,500,350],'foot':[450,350]}}
    detector=ContactDetector('badminton')
    machine=RallyMachine('badminton')
    machine.step([event('hit',0,player='B')],0)
    contacts=[]
    for index,y in enumerate([400,440,480,600,601,600]):
        timestamp=(index+1)*.1
        contacts=detector.update(Detection([698,y-2,702,y+2],.95),players,timestamp,court,(1000,1000,3))
        machine.observe_ball(timestamp)
        machine.step(contacts,timestamp)
    assert contacts and contacts[0].kind == 'landing'
    decision=machine.step([],.7)
    assert decision.winner == 'B' and decision.status == 'confirmed'

def test_tennis_bounce_and_apex_are_distinct():
    court=Court('tennis',[[.1,.1],[.9,.1],[.9,.9],[.1,.9]],(1000,1000,3))
    players={'B':{'box':[300,150,400,350],'foot':[350,350]}}
    for heights,expected in [([300,350,400,350,300],True),([400,350,300,350,400],False)]:
        detector=ContactDetector('tennis')
        events=[]
        for index,y in enumerate(heights):
            events+=detector.update(Detection([698,y-2,702,y+2],.95),players,index*.1,court,(1000,1000,3))
        assert bool(events) == expected

def test_homography_uncertainty_band():
    court=Court('tennis',[[.1,.1],[.9,.1],[.9,.9],[.1,.9]],(1000,1000,3))
    assert court.landing((500,500))[1] is True
    assert court.landing((50,500))[1] is False
    assert court.landing((100,500),uncertainty_px=5)[1] is None

def test_interpolation_is_bounded_and_never_bridges_missing_ball():
    previous={'time':0,'players':{},'ball':Detection([0,0,4,4],.9),'generation':0}
    current={'time':.2,'players':{},'ball':Detection([20,0,24,4],.9),'generation':0}
    _,ball=interpolate_tracks(previous,current,.1)
    assert ball.center == (12,2)
    current['ball']=None
    assert interpolate_tracks(previous,current,.1)[1] is None
    current['time']=2
    assert interpolate_tracks(previous,current,1) == ({},None)
