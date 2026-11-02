from types import SimpleNamespace

from app.modules.rounds.service import GameRound, PlayerGuess

SPOT = SimpleNamespace(pano_id="p", lat=0.0, lng=0.0)
GUESS = PlayerGuess(lat=0.0, lng=0.0, distance_km=0.0)


def test_first_guess_leaves_the_others_ten_seconds():
    game_round = GameRound(number=1, location=SPOT, players={1, 2, 3})
    assert game_round.seconds_left() > 55
    game_round.submit(1, GUESS)
    assert 9 < game_round.seconds_left() <= 10
    game_round.submit(2, GUESS)   # a later guess doesn't add time back
    assert game_round.seconds_left() <= 10 and not game_round.finished


def test_a_player_by_themselves_finishes_the_round_by_guessing():
    game_round = GameRound(number=1, location=SPOT, players={1})
    game_round.submit(1, GUESS)
    assert game_round.finished
