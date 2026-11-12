from types import SimpleNamespace

from app.modules.rounds.service import (
    FIRST_GUESS_SECONDS, ROUND_SECONDS, LobbyGame, PlayerGuess,
)
from app.scoring import NO_GUESS_PENALTY_KM, STARTING_POINTS, haversine_distance


def make_location(previous=None):
    make_location.count += 1
    return SimpleNamespace(pano_id=f"pano{make_location.count}", lat=0.0, lng=0.0)


make_location.count = 0


def guess_at(lat, lng):
    """True location in these tests is (0, 0)."""
    return PlayerGuess(lat=lat, lng=lng, distance_km=haversine_distance(0.0, 0.0, lat, lng))


def new_game(*player_ids):
    return LobbyGame.start("lobby", set(player_ids), make_location)


# timer: drops to 10 seconds after the first guess
def test_first_guess_drops_the_timer_to_ten_seconds():
    game = new_game(1, 2)
    assert game.current.seconds_left() > ROUND_SECONDS - 5
    game.guess(1, guess_at(0, 1))
    assert game.current.seconds_left() <= FIRST_GUESS_SECONDS
    assert not game.current.finished


def test_timer_is_never_extended():
    game = new_game(1, 2)
    game.current.started_at -= ROUND_SECONDS - 4        #4 seconds left
    game.guess(1, guess_at(0, 1))
    assert game.current.seconds_left() <= 4


def test_second_guess_does_not_reset_the_timer():
    game = new_game(1, 2, 3)
    game.guess(1, guess_at(0, 1))
    left = game.current.seconds_left()
    game.guess(2, guess_at(0, 2))
    assert game.current.seconds_left() <= left


def test_round_closes_when_the_short_timer_runs_out_and_late_player_is_penalized():
    game = new_game(1, 2)
    game.guess(1, guess_at(0, 1))
    game.current.started_at -= FIRST_GUESS_SECONDS + 1   # ten seconds pass
    game.refresh()
    assert game.current.finished
    assert game.points[1] == STARTING_POINTS
    assert game.points[2] == STARTING_POINTS - NO_GUESS_PENALTY_KM


# players leaving mid-game
def test_leaving_player_is_out_but_stays_on_the_scoreboard():
    game = new_game(1, 2, 3)
    game.remove_player(3)
    assert game.points[3] == 0
    assert 3 in game.eliminated and 3 not in game.current.players
    assert not game.over


def test_round_closes_when_the_missing_player_leaves():
    game = new_game(1, 2, 3)
    game.guess(1, guess_at(0, 1))
    game.guess(2, guess_at(0, 5))
    assert not game.current.finished                 #still waiting for player 3
    game.remove_player(3)
    assert game.current.finished
    assert game.points[1] == STARTING_POINTS         #closest guess loses nothing
    assert game.points[2] < STARTING_POINTS


def test_game_ends_when_only_one_player_is_left():
    game = new_game(1, 2)
    game.remove_player(2)
    assert game.over and game.winner == 1


def test_leaving_between_rounds_excludes_them_from_the_next_round():
    game = new_game(1, 2, 3)
    for pid, lng in ((1, 1), (2, 2), (3, 3)):
        game.guess(pid, guess_at(0, lng))
    assert game.current.finished
    game.remove_player(3)
    assert game.start_next(1, make_location).players == {1, 2}


def test_removing_an_unknown_player_or_after_game_over_does_nothing():
    game = new_game(1, 2)
    game.remove_player(99)
    assert game.points == {1: STARTING_POINTS, 2: STARTING_POINTS}
    game.remove_player(2)
    before = dict(game.points)
    game.remove_player(1)
    assert game.points == before
