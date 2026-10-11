"""Continuous identities and conservative image-space contact candidates."""
from collections import deque
import math
import numpy as np
from scipy.optimize import linear_sum_assignment
from .sports import RallyEvent

class TrackingEngine:
    def __init__(self, use_bytetrack=False, inference_fps=10):
        self.ball = deque(maxlen=60)
        self.players = {}
        self.last_contact = -10.0
        self.last_ball_time = -10.0
        self.object_speed = None
        self.ball_generation = 0
        self.identity = None
        if use_bytetrack:
            from .identity import PlayerIdentityTracker
            self.identity = PlayerIdentityTracker(inference_fps)

    def update(self, objects, people, timestamp, shape, court=None):
        height, width = shape[:2]
        diagonal = math.hypot(width, height)
        if court:
            # Filter officials and spectators before association, not only when
            # creating identities. They must not replace an established player.
            people = [p for p in people if court.contains(court.project(p.foot),tolerance=.8)]
        if self.identity:
            people = self.identity.update(people, shape)
        people = sorted(people, key=lambda p: p.confidence, reverse=True)[:8]
        self.players = {key: value for key, value in self.players.items()
                        if timestamp-value['time']<=2 and
                        (not court or court.contains(court.project(value['foot']),tolerance=.8))}
        assigned = set()
        if not self.players and not court and len(people) >= 2:
            pair = sorted(people[:2], key=lambda person: person.foot[1], reverse=True)
            for key, person in zip(('A', 'B'), pair):
                self.players[key] = self.player_record(person, timestamp)
        if self.players and people:
            ids = list(self.players)
            def association(key, person):
                previous = self.players[key]
                distance = math.dist(previous['foot'],person.foot)
                changed = person.track_id is not None and previous.get('track_id') not in (None,person.track_id)
                if changed:
                    # Reacquire a nearby observed player after a short gap even
                    # when ByteTrack starts a new ID. Never fabricate positions.
                    gap = timestamp-previous['time']
                    old_height = max(1,previous['box'][3]-previous['box'][1])
                    new_height = max(1,person.box[3]-person.box[1])
                    same_side = not court or court.side(court.project(previous['foot']))==court.side(court.project(person.foot))
                    plausible = gap>=.2 and distance<diagonal*.10 and .5<new_height/old_height<2 and same_side
                    distance += diagonal*(.03 if plausible else 1)
                return distance
            costs = np.array([[association(key,person) for person in people] for key in ids])
            rows, columns = linear_sum_assignment(costs)
            for row, col in zip(rows, columns):
                if costs[row, col] < diagonal * 0.22:
                    key = ids[row]
                    self.players[key] = self.player_record(people[col], timestamp)
                    assigned.add(col)
        for index, person in enumerate(people):
            if index in assigned or len(self.players) >= 2:
                continue
            if court:
                ground = court.project(person.foot)
                if not (-court.width*.2 <= ground[0] <= court.width*1.2 and -court.length*.15 <= ground[1] <= court.length*1.15):
                    continue
                key = court.side(ground)
            else:
                key = 'A' if person.foot[1] >= height / 2 else 'B'
            if key not in self.players:
                self.players[key] = self.player_record(person, timestamp)
        current = {key: value for key, value in self.players.items() if value['time'] == timestamp}
        if timestamp - self.last_ball_time > 0.6:
            if self.ball:
                self.ball_generation += 1
            self.ball.clear()
            self.object_speed = None
        candidates = objects
        if self.ball:
            prediction = np.array(self.ball[-1]['point'])
            if len(self.ball) > 1:
                previous, last = self.ball[-2], self.ball[-1]
                dt = last['time'] - previous['time']
                if dt > 0:
                    prediction += (np.array(last['point']) - previous['point']) * min((timestamp-last['time']) / dt, 3)
            candidates = [obj for obj in objects if math.dist(obj.center, prediction) < diagonal * 0.2]
            selected = min(candidates, key=lambda obj: math.dist(obj.center, prediction) / diagonal - obj.confidence * 0.05) if candidates else None
        else:
            candidates = [obj for obj in candidates if obj.confidence >= .25]
            selected = max(candidates, key=lambda obj: obj.confidence) if candidates else None
        events = []
        if selected:
            point = selected.center
            if self.ball:
                dt = timestamp - self.ball[-1]['time']
                self.object_speed = math.dist(point, self.ball[-1]['point']) / dt if 0 < dt <= .35 else None
            self.ball.append({'point': list(point), 'time': timestamp, 'confidence': selected.confidence})
            self.last_ball_time = timestamp
        return current, selected, events

    @staticmethod
    def player_record(person, timestamp):
        return {'foot': person.foot, 'box': person.box, 'keypoints': person.keypoints,
                'time': timestamp, 'track_id': person.track_id}

# Public compatibility import: tracking and coaching share observed player records.
from .coaching import AnalyticsEngine
