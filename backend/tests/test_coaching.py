from types import SimpleNamespace
import pytest
from app.coaching import AnalyticsEngine
from app.court import Court
from app.sports import RallyEvent


@pytest.fixture
def court():
    return Court('badminton', [[0,0],[1,0],[1,1],[0,1]], (1340,518,3))


def players(x=2, y=8, identity=1):
    return {'A': {'foot':[x*100,y*100], 'track_id':identity}}


def hit(t, player='A'):
    return RallyEvent('hit',t,.9,player=player)


def finish(engine,t,identity='rally'):
    engine.update({},[],t,None,rally_state='RALLY_ENDED',
                  decision=SimpleNamespace(id=identity,time=t,winner='A'))


def test_no_calibration_does_not_invent_distance():
    engine=AnalyticsEngine()
    engine.update(players(),[hit(0)],0,None)
    engine.update(players(3),[],.2,None)
    result=engine.snapshot(.2)
    assert result['distance_m']['A'] is None
    assert result['sprints']['A'] is None
    assert result['peak_shot_kmh'] is None


def test_distance_uses_real_court_scale(court):
    engine=AnalyticsEngine()
    engine.update(players(),[hit(0)],0,court)
    engine.update(players(2.4),[],.2,court)
    assert engine.snapshot(.2)['distance_m']['A']==pytest.approx(.4)


def test_zone_percentages_weight_seconds_not_samples(court):
    engine=AnalyticsEngine()
    for i in range(11):
        engine.update(players(y=7.5),[hit(0)] if i==0 else [],i/10,court)
    # A tracking gap starts a new segment; nine samples cover four rear-court seconds.
    for i in range(9):
        engine.update(players(y=12),[],2+i/2,court)
    assert engine.snapshot(6)['zone_split']['A']['net_pct']==20


def test_zone_split_mirrors_both_ends_and_weights_time(court):
    engine=AnalyticsEngine()
    for t in [0,.1,.4,.5]:
        observed={**players(y=7.5),'B':{'foot':[200,590],'track_id':2}}
        engine.update(observed,[hit(0)] if t==0 else [],t,court)
    result=engine.snapshot(.5)
    for key in ('A','B'):
        assert result['zone_split'][key]['net_pct']==100
        assert result['zone_split'][key]['observed_seconds']==.5


@pytest.mark.parametrize('new_time,identity,interpolated',[(2,1,False),(.2,2,False),(.2,1,True)])
def test_gaps_swaps_and_interpolation_do_not_add_distance(court,new_time,identity,interpolated):
    engine=AnalyticsEngine()
    engine.update(players(),[hit(0)],0,court)
    observed=players(3,identity=identity)
    observed['A']['interpolated']=interpolated
    engine.update(observed,[],new_time,court)
    assert engine.snapshot(new_time)['distance_m']['A'] is None


def test_sprints_require_sustained_burst_and_recovery(court):
    engine=AnalyticsEngine()
    for t,x in [(0,1),(.1,1.4),(.2,1.8),(.3,2.2),(.4,2.6),(.5,2.6),(.6,2.6),(.7,2.6),(.8,3),(.9,3.4),(1,3.8)]:
        engine.update(players(x),[hit(0)] if t==0 else [],t,court)
    result=engine.snapshot(1)
    assert result['sprints']['A']==2
    assert result['high_intensity_seconds']['A']==.7
    assert result['work_rate_pct']['A']==70


def test_single_fast_sample_is_not_a_sprint(court):
    engine=AnalyticsEngine()
    engine.update(players(),[hit(0)],0,court)
    engine.update(players(2.4),[],.1,court)
    engine.update(players(2.4),[],.4,court)
    assert engine.snapshot(.4)['sprints']['A']==0


def test_rallies_rest_distribution_and_deduplication():
    engine=AnalyticsEngine()
    for start,count in [(0,4),(10,6),(25,11)]:
        for i in range(count):
            engine.update({},[hit(start+i*.2)],start+i*.2,None,rally_state='IN_RALLY')
        finish(engine,start+4,str(start))
        finish(engine,start+4,str(start))
    report=engine.snapshot(29)
    assert report['rally_distribution']=={'short':1,'medium':1,'marathon':1}
    assert report['rally_count']==3
    assert report['average_rally_seconds']==4
    assert report['rest_seconds']==17
    assert report['work_rest_ratio']==pytest.approx(.71)
    assert report['rally_pace_spm']==90


def test_interrupted_rally_is_not_completed():
    engine=AnalyticsEngine()
    engine.update({},[hit(0)],0,None,rally_state='IN_RALLY')
    engine.update({},[],5,None,rally_state='WAITING_FOR_SERVE')
    assert engine.snapshot(5)['rally_count']==0
    assert engine.snapshot(5)['average_rally_seconds'] is None


def test_cutaway_does_not_create_recovery_time():
    engine=AnalyticsEngine()
    engine.update({},[hit(0)],0,None)
    finish(engine,4,'one')
    engine.update({},[],8,None,play_visible=False)
    engine.update({},[hit(20)],20,None)
    finish(engine,24,'two')
    assert engine.snapshot(24)['rest_seconds']==0


def test_only_validated_3d_flight_produces_shot_speed():
    engine=AnalyticsEngine()
    engine.observe_metric_shot([0,0],0,validated=True)
    engine.observe_metric_shot([10,0],.1,validated=True)
    assert engine.snapshot(.1)['peak_shot_kmh'] is None
    engine.observe_metric_shot([0,0,1],1,validated=True,track_id=1)
    engine.observe_metric_shot([2,0,1],1.1,validated=True,track_id=1)
    assert engine.snapshot(1.1)['peak_shot_kmh']==72
    engine.observe_metric_shot([20,0,1],1.2,validated=True,track_id=2)
    assert engine.snapshot(1.2)['peak_shot_kmh']==72


def test_weak_hit_is_not_counted():
    engine=AnalyticsEngine()
    engine.update({},[RallyEvent('hit',0,.2,player='A')],0,None)
    finish(engine,5)
    assert engine.snapshot(5)['rally_count']==0


def test_visibility_excludes_skipped_frames_and_warns_about_partial_view():
    engine=AnalyticsEngine()
    for i in range(20):
        engine.update(players(),[],i*.1,None,observation_sample=True)
        engine.update({},[],i*.1+.05,None,observation_sample=False)
    report=engine.snapshot(2)
    assert report['player_visibility_pct']=={'A':100,'B':0}
    assert any('Player B is visible in only 0%' in tip for tip in report['coaching_advice'])


def test_sprint_creates_a_real_review_timestamp(court):
    engine=AnalyticsEngine()
    for i in range(5):
        engine.update(players(x=1+i*.4),[hit(2)] if i==0 else [],2+i*.1,court)
    moments=engine.snapshot(2.4)['review_moments']
    assert len(moments)==1
    assert moments[0]['time']==2
    assert 'Player A' in moments[0]['title']
