"""Observed-contact extraction and an explicit, exactly-once rally state machine.

Ground contacts are multi-frame visual hypotheses, not 3D measurements.
Interpolated or missing observations are never accepted as contact evidence.
"""
from collections import deque
from dataclasses import dataclass
from enum import Enum
import math
import numpy as np
from .sports import SPORTS, RallyEvent


class RallyState(str, Enum):
    WAITING_FOR_SERVE = 'WAITING_FOR_SERVE'
    IN_RALLY = 'IN_RALLY'
    RALLY_ENDED = 'RALLY_ENDED'
    UPDATE_SCORE = 'UPDATE_SCORE'


@dataclass
class RallyDecision:
    id: str
    time: float
    winner: str | None
    confidence: float
    status: str
    reason: str


class RallyMachine:
    def __init__(self, sport, auto_score=True, threshold=0.75):
        self.sport_name = sport
        self.rules = SPORTS[sport]()
        self.state = RallyState.WAITING_FOR_SERVE
        self.auto_score, self.threshold = auto_score, threshold
        self.rally_id = 0
        self.last_seen = None
        self.ended_at = -10.0
        self.pending = None
        self.seen = set()
        self.reason = 'Waiting for an observed hit'

    def observe_ball(self, timestamp):
        self.last_seen = timestamp

    def step(self, events, timestamp):
        decision = None
        if self.state == RallyState.RALLY_ENDED:
            self.state = RallyState.UPDATE_SCORE
            decision, self.pending = self.pending, None
        elif self.state == RallyState.UPDATE_SCORE and timestamp - self.ended_at >= 1.0:
            self.state = RallyState.WAITING_FOR_SERVE
            self.rules = SPORTS[self.sport_name]()
            self.reason = 'Waiting for the next rally'
        elif self.state == RallyState.IN_RALLY and self.last_seen is not None and timestamp - self.last_seen > 1.8:
            # Ball tracking lost without confirmed ground landing.
            # Do NOT award points on lost tracks; only count points on shuttlecock ground contact.
            self.state = RallyState.WAITING_FOR_SERVE
            self.rules = SPORTS[self.sport_name]()
            self.reason = 'Rally ended: track lost without confirmed ground touch'

        for event in events:
            token = (event.kind, round(event.time, 4), event.player)
            if token in self.seen:
                continue
            self.seen.add(token)
            if self.state in (RallyState.RALLY_ENDED, RallyState.UPDATE_SCORE):
                continue
            if self.state == RallyState.WAITING_FOR_SERVE:
                if event.kind != 'hit' or not event.player or event.confidence < 0.5:
                    continue
                self.rally_id += 1
                self.state = RallyState.IN_RALLY
                self.last_seen = event.time
                self.reason = f'Rally {self.rally_id}: hit by Player {event.player}'
            
            winner = self.rules.interpret(event)
            if event.kind == 'hit':
                self.reason = f'Hit: Player {event.player}'
                self.last_seen = event.time
            elif event.grounded:
                self.reason = event.evidence or event.kind
            
            if winner:
                quality = max(0.85, getattr(self.rules, 'decision_confidence', 0.90))
                status = 'confirmed' if self.auto_score else 'review'
                self.pending = RallyDecision(f'rally-{self.rally_id}', event.time, winner, quality, status, self.reason)
                self.state = RallyState.RALLY_ENDED
                self.ended_at = event.time
        return decision


class ContactDetector:
    """Separate hits, downward-to-upward bounces and settled shuttle landings."""
    def __init__(self, sport):
        self.sport = sport
        self.samples = deque(maxlen=7)
        self.last_contact = -10.0

    @staticmethod
    def hitter(point, players):
        candidates = []
        for key, player in players.items():
            x1, y1, x2, y2 = player['box']
            height = y2 - y1
            # Include overhead smashes, serves, and low volleys around player reach
            if x1 - height * 0.7 <= point[0] <= x2 + height * 0.7 and y1 - height * 0.75 <= point[1] <= y2 + height * 0.15:
                center = ((x1+x2)/2, (y1+y2)/2)
                candidates.append((math.dist(point, center), key))
        return min(candidates)[1] if candidates else None

    @staticmethod
    def side_owner(point, players, court):
        if court is None or point is None:
            return None
        try:
            side = court.side(point)
            owners = [key for key, player in players.items() if court.side(court.project(player['foot'])) == side]
            return owners[0] if len(owners) == 1 else None
        except Exception:
            return None

    def update(self, ball, players, timestamp, court, shape):
        if ball is None:
            if self.samples and timestamp - self.samples[-1]['time'] > .45:
                self.samples.clear()
            return []
        if self.samples and timestamp - self.samples[-1]['time'] > .45:
            self.samples.clear()
        self.samples.append({'point': np.array(ball.center), 'time': timestamp, 'confidence': ball.confidence})
        if len(self.samples) < 4 or timestamp - self.last_contact < .20:
            return []
        samples = list(self.samples)
        points = np.array([sample['point'] for sample in samples])
        times = np.array([sample['time'] for sample in samples])
        if np.any(np.diff(times) <= 0):
            return []
        quality = float(min(sample['confidence'] for sample in samples[-4:]))
        if quality < .12:
            return []
        
        mid_idx = max(1, len(samples) // 2)
        before = (points[mid_idx] - points[0]) / max(times[mid_idx] - times[0], 1e-4)
        after = (points[-1] - points[mid_idx]) / max(times[-1] - times[mid_idx], 1e-4)
        speed_before, speed_after = np.linalg.norm(before), np.linalg.norm(after)
        minimum_speed = max(30.0, shape[0] * .05)
        turn = float(np.dot(before, after) / max(speed_before * speed_after, 1e-6))
        
        hitter = self.hitter(points[mid_idx], players)
        if speed_before > minimum_speed and speed_after > minimum_speed and turn < .60 and hitter:
            confidence = min(.98, .65 + .25 * (1-turn)/2 + .1 * quality)
            self.last_contact = timestamp
            return [RallyEvent('hit', float(times[mid_idx]), confidence, player=hitter, evidence='Observed reversal near player racket region')]

        contact_point = points[mid_idx]
        contact_time = times[mid_idx]
        side = 'A' if contact_point[1] >= shape[0] * 0.5 else 'B'
        inside = True
        ground = None

        if court:
            try:
                ground, inside_call = court.landing(contact_point, uncertainty_px=max(2, shape[1]*.003))
                if inside_call is not None:
                    inside = inside_call
                owner = self.side_owner(ground, players, court)
                if owner:
                    side = owner
            except Exception:
                pass

        down_motion = before[1] > minimum_speed * 0.25
        up_motion = after[1] < -minimum_speed * 0.25

        if self.sport == 'tennis':
            if down_motion and (up_motion or turn < 0.35) and not hitter:
                confidence = min(.96, .70 + .15 * quality)
                self.last_contact = timestamp
                return [RallyEvent('bounce', float(contact_time), confidence, side=side, inside=inside,
                                   grounded=True, court_point=ground, evidence='Tennis court bounce')]
        elif self.sport == 'badminton':
            # STRICT BADMINTON GROUND CONTACT:
            # 1. Floor region: must be at or below 30% of frame height (cannot be mid-air / ceiling)
            # 2. Downward trajectory: shuttlecock was descending towards the floor
            # 3. Not a player hit: player is not swinging or making contact
            # 4. Settle on floor: speed drops to near zero as it settles
            at_floor_level = contact_point[1] >= shape[0] * 0.30
            if court and ground:
                try:
                    at_floor_level = at_floor_level and court.contains(ground, tolerance=2.5)
                except Exception:
                    pass

            settled_speed = float(np.linalg.norm(after))
            is_landing = (
                at_floor_level
                and down_motion
                and not hitter
                and settled_speed < minimum_speed * 1.2
            )
            if is_landing:
                confidence = min(.96, .75 + .15 * quality)
                self.last_contact = timestamp
                return [RallyEvent('landing', float(contact_time), confidence, side=side, inside=inside,
                                   grounded=True, court_point=ground, evidence='Shuttlecock court landing')]
        return []
