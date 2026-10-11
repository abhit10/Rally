"""Coaching summaries from calibrated, observed movement and completed rallies.

Missing calibration is missing information, never an assumed metric scale.
Position alone does not identify strokes, backhands, fatigue or calories burned.
"""
from collections import deque
import math
import numpy as np


class AnalyticsEngine:
    VERSION = 2

    def __init__(self, sport='tennis'):
        self.sport = sport
        self.positions = {key: deque(maxlen=1200) for key in ('A','B')}
        self.last = {}
        self.distance = dict.fromkeys(('A','B'),0.0)
        self.speed = dict.fromkeys(('A','B'),None)
        self.observed_seconds = dict.fromkeys(('A','B'),0.0)
        self.zone_seconds = {key:{'net':0.0,'rear':0.0} for key in ('A','B')}
        self.sprints = dict.fromkeys(('A','B'),0)
        self.high_seconds = dict.fromkeys(('A','B'),0.0)
        self.burst_seconds = dict.fromkeys(('A','B'),0.0)
        self.burst_counted = dict.fromkeys(('A','B'),False)
        self.recovery_seconds = dict.fromkeys(('A','B'),0.0)
        self.active_seconds = dict.fromkeys(('A','B'),0.0)
        self.hits = 0
        self.seen_hits = set()
        self.completed_ids = set()
        self.current = None
        self.rally_records = []
        self.last_end = None
        self.rest_seconds = 0.0
        self.rest_continuous = False
        self.pending_rest = 0.0
        self.calibrated = False
        self.shot_last = None
        self.shot_top = None
        self.shot_sum = self.shot_time = 0.0
        self.visibility_samples = 0
        self.visible_samples = dict.fromkeys(('A','B'),0)
        self.last_sample_time = None
        self.review_moments = deque(maxlen=20)

    def observe_metric_shot(self, position_m, timestamp, *, validated=False, track_id=None):
        """Optional measured 3D input. Never feed an airborne homography here."""
        if not validated or len(position_m) != 3 or not np.isfinite(position_m).all():
            self.shot_last = None
            return
        if self.shot_last:
            old, old_time, old_id = self.shot_last
            dt = timestamp-old_time
            if old_id == track_id and .005 <= dt <= .25:
                meters = math.dist(old,position_m)
                kmh = meters/dt*3.6
                if 0 <= kmh <= 600:
                    self.shot_top = max(self.shot_top or 0,kmh)
                    self.shot_sum += meters*3.6
                    self.shot_time += dt
        self.shot_last = (list(position_m),timestamp,track_id)

    def _reset_burst(self, key):
        self.burst_seconds[key] = 0.0
        self.burst_counted[key] = False
        self.recovery_seconds[key] = 0.0

    def _movement(self, players, timestamp, court, in_rally, image_shape=None):
        for key in ('A','B'):
            self.speed[key] = None
            player = players.get(key)
            if not player or player.get('interpolated'):
                self.last.pop(key,None)
                self._reset_burst(key)
                continue
            if not court:
                if image_shape:
                    h, w = image_shape[:2]
                    self.positions[key].append([
                        min(1.0, max(0.0, player['foot'][0] / max(w, 1))),
                        min(1.0, max(0.0, player['foot'][1] / max(h, 1)))
                    ])
                self.last.pop(key,None)
                self._reset_burst(key)
                continue
            point = court.project(player['foot'])
            if not np.isfinite(point).all() or not court.contains(point,tolerance=2.5):
                self.last.pop(key,None)
                self._reset_burst(key)
                continue
            self.positions[key].append([point[0]/court.width,point[1]/court.length])
            old = self.last.get(key)
            self.last[key] = (point,timestamp,player.get('track_id'),in_rally)
            if old is None:
                self._reset_burst(key)
                continue
            previous, old_time, identity, was_active = old
            dt = timestamp-old_time
            movement = math.dist(previous,point)
            if not 0 < dt <= .5 or identity != player.get('track_id') or movement/dt > 12:
                self._reset_burst(key)
                continue
            speed = movement/dt
            self.distance[key] += movement
            self.observed_seconds[key] += dt
            self.speed[key] = speed
            if not (in_rally and was_active):
                self._reset_burst(key)
                continue
            self.active_seconds[key] += dt
            midpoint = [(a+b)/2 for a,b in zip(previous,point)]
            if court.contains(midpoint):
                # Front 35% of each player's half, measured away from the net.
                depth = abs(midpoint[1]-court.length/2)/(court.length/2)
                self.zone_seconds[key]['net' if depth <= .35 else 'rear'] += dt
            if speed > 3.2:
                self.high_seconds[key] += dt
                self.burst_seconds[key] += dt
                self.recovery_seconds[key] = 0
                if self.burst_seconds[key] >= .3-1e-9 and not self.burst_counted[key]:
                    self.sprints[key] += 1
                    self.burst_counted[key] = True
                    self.review_moments.append({'time':round(max(0,timestamp-self.burst_seconds[key]),2),
                                                'title':f'Player {key} · quick court movement',
                                                'detail':'Review the first step, balance at contact and recovery after this burst.'})
            elif speed < 2.7:
                self.recovery_seconds[key] += dt
                if self.recovery_seconds[key] >= .3-1e-9:
                    self.burst_seconds[key] = 0
                    self.burst_counted[key] = False
            else:
                self.recovery_seconds[key] = 0

    def update(self, players, events, timestamp, court, image_shape=None,
               rally_state=None, decision=None, play_visible=True, observation_sample=True):
        self.calibrated = court is not None
        if observation_sample and play_visible and timestamp != self.last_sample_time:
            self.last_sample_time = timestamp
            self.visibility_samples += 1
            for key in ('A','B'):
                if players.get(key) and not players[key].get('interpolated'):
                    self.visible_samples[key] += 1
        if not play_visible:
            self.current = None
            self.pending_rest = 0
            self.rest_continuous = False
            self.last.clear()
        for event in events:
            if event.kind != 'hit' or event.player not in ('A','B') or event.confidence < .5:
                continue
            token = (round(event.time,4),event.player)
            if token in self.seen_hits:
                continue
            self.seen_hits.add(token)
            self.hits += 1
            if rally_state not in (None,'IN_RALLY') or not play_visible:
                continue
            if self.current is None:
                self.current = {'start':event.time,'shots':0,'last_hit':event.time}
                self.pending_rest = max(0,event.time-self.last_end) if self.last_end is not None and self.rest_continuous else 0
            self.current['shots'] += 1
            self.current['last_hit'] = event.time
        in_rally = self.current is not None and rally_state in (None,'IN_RALLY','RALLY_ENDED') and play_visible
        self._movement(players,timestamp,court,in_rally,image_shape)
        if decision is not None and decision.id not in self.completed_ids:
            self.completed_ids.add(decision.id)
            if self.current and decision.time >= self.current['start']:
                duration = decision.time-self.current['start']
                self.rally_records.append({'duration_s':round(duration,3),'shots':self.current['shots'],
                                           'winner':decision.winner,'start':self.current['start'],'end':decision.time})
                self.rest_seconds += self.pending_rest
                self.last_end = decision.time
                self.rest_continuous = play_visible
            self.current = None
            self.pending_rest = 0
        elif self.current and rally_state == 'WAITING_FOR_SERVE':
            duration = self.current['last_hit'] - self.current['start']
            if self.current['shots'] >= 2 and duration >= 0.8:
                self.rally_records.append({'duration_s':round(duration,3),'shots':self.current['shots'],
                                           'winner':None,'start':self.current['start'],'end':self.current['last_hit']})
                self.rest_seconds += self.pending_rest
                self.last_end = self.current['last_hit']
                self.rest_continuous = play_visible
            self.current = None
            self.pending_rest = 0
            self.rest_continuous = False

    def finalize(self, timestamp):
        if self.current and self.current['shots'] >= 2:
            duration = max(0.8, timestamp - self.current['start'])
            self.rally_records.append({'duration_s':round(duration,3),'shots':self.current['shots'],
                                       'winner':None,'start':self.current['start'],'end':timestamp})
            self.current = None

    def snapshot(self, timestamp):
        zone_split = {}
        for key in ('A','B'):
            total = sum(self.zone_seconds[key].values())
            net = round(100*self.zone_seconds[key]['net']/total,1) if total else None
            zone_split[key] = {'net_pct':net,'rear_pct':round(100-net,1) if net is not None else None,
                               'observed_seconds':round(total,2)}
        durations = [r['duration_s'] for r in self.rally_records]
        if not durations and self.current and self.current['shots'] >= 2:
            current_duration = round(max(0.8, timestamp - self.current['start']), 3)
            durations = [current_duration]
            work = current_duration
            shots = self.current['shots']
            longest = {'duration_s': current_duration, 'shots': shots, 'start': self.current['start']}
            distribution = {'short': 1 if shots <= 4 else 0, 'medium': 1 if 4 < shots <= 10 else 0, 'marathon': 1 if shots > 10 else 0}
        else:
            work = sum(durations)
            shots = sum(r['shots'] for r in self.rally_records)
            longest = max(self.rally_records,key=lambda r:r['duration_s']) if self.rally_records else None
            distribution = {'short':0,'medium':0,'marathon':0}
            for rally in self.rally_records:
                distribution['short' if rally['shots'] <= 4 else 'medium' if rally['shots'] <= 10 else 'marathon'] += 1
        advice = []
        visibility = {key:round(100*self.visible_samples[key]/self.visibility_samples,1) if self.visibility_samples else None for key in ('A','B')}
        for key in ('A','B'):
            if self.visibility_samples >= 20 and visibility[key]<70:
                advice.append(f'Player {key} is visible in only {visibility[key]:.0f}% of reviewed moments. Use a higher, centered camera view with both baselines visible before comparing player workloads.')
        if not self.calibrated:
            advice.append('Mark the four court corners to unlock distance, sprint counts and court-position insights.')
        for key in ('A','B'):
            zone = zone_split[key]
            if zone['observed_seconds'] >= 5:
                net = zone['net_pct']
                if net >= 50:
                    advice.append(f'Player {key} spent {net:.0f}% of observed rally time near the net. Review recovery steps after attacking the front court.')
                else:
                    advice.append(f'Player {key} spent {100-net:.0f}% of observed rally time in the rear court. Practice moving forward behind a well-placed attacking shot.')
        if len(durations) >= 3:
            if distribution['marathon'] > len(durations)/3:
                advice.append('Long exchanges are common. Practice repeated rally efforts with the measured recovery time between sets of drills.')
            else:
                advice.append('Review the opening four shots of each rally to identify opportunities to build pressure earlier.')
        if not advice:
            advice.append('Finish a few rallies to build a useful coaching report.')
        front_leader = None
        if all(zone_split[k]['observed_seconds'] >= 5 and (visibility[k] or 0)>=70 for k in ('A','B')):
            gap = zone_split['A']['net_pct']-zone_split['B']['net_pct']
            if abs(gap) >= 10:
                front_leader = 'A' if gap > 0 else 'B'
        return {
            'version':self.VERSION,'calibrated':self.calibrated,
            'player_visibility_pct':visibility,
            'review_moments':([{'time':longest['start'],'title':f'Longest rally · {longest["duration_s"]:.1f}s',
                                'detail':f'{longest["shots"]} observed shots. Compare recovery position early and late in the exchange.'}] if longest else [])+list(self.review_moments)[-7:],
            'distance_m':{k:round(self.distance[k],1) if self.observed_seconds[k] else None for k in ('A','B')},
            'speed_mps':{k:round(self.speed[k],2) if self.speed[k] is not None else None for k in ('A','B')},
            'heatmap':{k:list(v) for k,v in self.positions.items()},
            'trajectory':{k:list(v) for k,v in self.positions.items()},
            'zone_split':zone_split,'front_court_leader':front_leader,
            'sprints':{k:self.sprints[k] if self.active_seconds[k] else None for k in ('A','B')},
            'high_intensity_seconds':{k:round(self.high_seconds[k],1) if self.active_seconds[k] else None for k in ('A','B')},
            'work_rate_pct':{k:round(100*self.high_seconds[k]/self.active_seconds[k],1) if self.active_seconds[k] else None for k in ('A','B')},
            'estimated_hits':self.hits,'rally_seconds':round(max(0,timestamp-self.current['start']),1) if self.current else 0,
            'rallies':durations[-40:],'rally_count':len(durations),'longest_rally':longest,
            'average_rally_seconds':round(work/len(durations),1) if durations else None,
            'rally_distribution':distribution,'work_seconds':round(work,1),'rest_seconds':round(self.rest_seconds,1),
            'work_rest_ratio':round(work/self.rest_seconds,2) if work and self.rest_seconds else None,
            'rally_pace_spm':round(max(0,shots-len(durations))/work*60,1) if work else None,
            'peak_shot_kmh':round(self.shot_top,1) if self.shot_top is not None else None,
            'average_shot_kmh':round(self.shot_sum/self.shot_time,1) if self.shot_time else None,
            'shot_speed_note':'Shot speed needs reliable ball-flight measurements.',
            'coaching_advice':advice,
        }
