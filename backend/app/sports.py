"""Sport plugins and replayable point ledgers for singles matches."""
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class RallyEvent:
    kind: str
    time: float
    confidence: float
    player: str | None = None
    side: str | None = None
    inside: bool | None = None
    grounded: bool = False
    court_point: list[float] | None = None
    evidence: str = ''

def opponent(player):
    return 'B' if player == 'A' else 'A'

class SportModule(ABC):
    def __init__(self):
        self.last_hitter = None
        self.bounces = 0
        self.rally_open = False
        self.rally_confidence = 0.0
        self.decision_confidence = 0.0

    @abstractmethod
    def interpret(self, event): ...

    @abstractmethod
    def scoreboard(self, winners): ...

class Tennis(SportModule):
    def __init__(self):
        super().__init__()
        self.bounces = 0

    def interpret(self, event):
        if event.kind == 'hit' and event.player:
            self.last_hitter = event.player
            self.bounces = 0
            self.rally_open = True
            self.rally_confidence = event.confidence
            return None

        if event.kind != 'bounce' or not event.grounded or not self.rally_open or not self.last_hitter:
            return None

        if self.bounces == 0:
            if event.inside is False:
                self.rally_open = False
                self.decision_confidence = min(0.95, self.rally_confidence * event.confidence)
                return opponent(self.last_hitter)
            if event.inside is True:
                self.bounces = 1
                return None
            return None

        if self.bounces == 1:
            self.rally_open = False
            self.decision_confidence = min(0.95, self.rally_confidence * event.confidence)
            return self.last_hitter

        return None

    def scoreboard(self, winners):
        points, games, sets = [0, 0], [0, 0], [0, 0]
        history, complete = [], False
        for winner in winners:
            if complete:
                break
            p = 0 if winner == 'A' else 1
            q = 1 - p
            points[p] += 1
            tiebreak = games == [6, 6]
            target = 7 if tiebreak else 4
            if points[p] >= target and points[p] - points[q] >= 2:
                games[p] += 1
                points = [0, 0]
                if (games[p] >= 6 and games[p] - games[q] >= 2) or games[p] == 7:
                    history.append(games[:])
                    sets[p] += 1
                    games = [0, 0]
                    complete = sets[p] == 2
        if games == [6, 6]:
            display = [str(x) for x in points]
        elif min(points) >= 3:
            display = ['40', '40'] if points[0] == points[1] else ['AD' if x == max(points) else '40' for x in points]
        else:
            display = [str([0, 15, 30, 40][min(x, 3)]) for x in points]
        return {'points': display, 'games': games, 'sets': sets, 'history': history, 'complete': complete, 'format': 'Best of 3 sets · 7-point tiebreak at 6–6'}

class Badminton(SportModule):
    def __init__(self):
        super().__init__()
        self.rally_hits = 0

    def interpret(self, event):
        # Track active hits in the rally
        if event.kind == 'hit' and event.player:
            self.last_hitter = event.player
            self.rally_open = True
            self.rally_hits += 1
            self.rally_confidence = event.confidence
            return None

        # STRICT REQUIREMENT: Only count a point when the shuttlecock touches the ground
        if event.kind != 'landing' or not event.grounded or not self.rally_open or not self.last_hitter:
            return None

        # At least one hit must have occurred in the rally
        if self.rally_hits < 1:
            return None

        # Line call uncertainty: if inside is None (unknown), cannot award point automatically
        if event.inside is None:
            return None

        self.rally_open = False
        self.decision_confidence = min(0.95, self.rally_confidence * event.confidence)

        # Shuttlecock landed OUT: the hitter hit it out -> opponent wins point
        if event.inside is False:
            return opponent(self.last_hitter)

        # Shuttlecock landed IN on a player's side: receiver failed to return -> opponent wins point
        if event.side:
            return opponent(event.side)

        # Fallback: hitter won the point on ground touch
        return self.last_hitter

    def scoreboard(self, winners):
        points, sets, history = [0, 0], [0, 0], []
        complete = False
        for winner in winners:
            if complete:
                break
            p = 0 if winner == 'A' else 1
            points[p] += 1
            if (points[p] >= 21 and points[p] - points[1-p] >= 2) or points[p] == 30:
                history.append(points[:])
                sets[p] += 1
                points = [0, 0]
                complete = sets[p] == 2
        return {'points': [str(x) for x in points], 'games': sets, 'sets': sets, 'history': history, 'complete': complete, 'format': 'Best of 3 games · 21 points · cap at 30'}

SPORTS = {'tennis': Tennis, 'badminton': Badminton}

def score_session(session):
    events = session.get('events', [])
    winners = [
        event['winner'] for event in events
        if event.get('winner') and (event.get('status') == 'confirmed' or event.get('automatic') is True)
    ]
    return SPORTS[session['sport']]().scoreboard(winners)
