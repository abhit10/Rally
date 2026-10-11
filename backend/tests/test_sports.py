from app.sports import Tennis, Badminton, RallyEvent

def test_tennis_deuce_advantage_and_game():
    sport = Tennis()
    tied = ['A', 'B'] * 3
    assert sport.scoreboard(tied)['points'] == ['40', '40']
    assert sport.scoreboard(tied + ['A'])['points'] == ['AD', '40']
    assert sport.scoreboard(tied + ['A', 'A'])['games'] == [1, 0]

def test_tennis_tiebreak_and_match():
    split_games = (['A'] * 4 + ['B'] * 4) * 6
    score = Tennis().scoreboard(split_games + ['A'] * 7)
    assert score['sets'] == [1, 0]
    assert score['history'] == [[7, 6]]
    assert Tennis().scoreboard(['A'] * 48)['complete']

def test_badminton_deuce_cap_and_match():
    tied = ['A', 'B'] * 20
    assert Badminton().scoreboard(tied + ['A'])['points'] == ['21', '20']
    assert Badminton().scoreboard(tied + ['A', 'A'])['history'] == [[22, 20]]
    assert Badminton().scoreboard(['A', 'B'] * 29 + ['B'])['history'] == [[29, 30]]
    assert Badminton().scoreboard(['A'] * 42)['complete']

def test_tennis_second_bounce_outside_still_awards_hitter():
    sport = Tennis()
    sport.interpret(RallyEvent('hit', 0, .99, player='A'))
    assert sport.interpret(RallyEvent('bounce', 1, .99, side='B', inside=True, grounded=True)) is None
    assert sport.interpret(RallyEvent('bounce', 2, .99, side='B', inside=False, grounded=True)) == 'A'
    assert sport.interpret(RallyEvent('bounce', 3, .99, side='B', inside=False, grounded=True)) is None

def test_ungrounded_contact_never_awards_point():
    sport = Badminton()
    sport.interpret(RallyEvent('hit', 0, .99, player='A'))
    assert sport.interpret(RallyEvent('landing', 1, .99, side='B', inside=True)) is None
    assert sport.interpret(RallyEvent('landing', 2, .99, side='B', inside=True, grounded=True)) == 'A'

def test_out_awards_opponent():
    for sport, kind in [(Tennis(), 'bounce'), (Badminton(), 'landing')]:
        sport.interpret(RallyEvent('hit', 0, .99, player='B'))
        assert sport.interpret(RallyEvent(kind, 1, .99, inside=False, grounded=True)) == 'A'

def test_unknown_landing_is_not_a_point():
    sport = Badminton()
    sport.interpret(RallyEvent('hit', 0, .99, player='A'))
    assert sport.interpret(RallyEvent('landing', 1, .99, side='B', grounded=True)) is None
