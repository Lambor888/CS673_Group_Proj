"""Tests for app/modules/rounds/service.py (pure logic, no server needed)."""
from types import SimpleNamespace

import pytest

from app.modules.rounds.service import (
    GameError, LobbyGame, PlayerGuess, SinglePlayerGame,
)
from app.scoring import (
    MAX_ROUND_SCORE, SINGLE_PLAYER_ROUNDS, STARTING_POINTS, haversine_distance,
    round_multiplier, single_player_round_score,
)


def make_location(previous=None):
    make_location.count += 1
    return SimpleNamespace(pano_id=f"pano{make_location.count}", lat=0.0, lng=0.0)


make_location.count = 0


def guess_at(lat, lng):
    """A guess at (lat, lng); the true location in these tests is always (0, 0)."""
    return PlayerGuess(lat=lat, lng=lng, distance_km=haversine_distance(0.0, 0.0, lat, lng))


def exact():
    return guess_at(0.0, 0.0)


def far():
    """About 10,000 km from the closest-possible guess: wipes out a full 10,000-point player."""
    return guess_at(0.0, 90.0)


def expire(game_round):
    game_round.started_at -= 10_000


def finish_round(game, *guesses_by_player):
    for pid, g in guesses_by_player:
        game.guess(pid, g)


# ---- single player ----------------------------------------------------------
def test_single_player_has_exactly_five_rounds():
    assert SINGLE_PLAYER_ROUNDS == 5
    game = SinglePlayerGame.start(1, make_location)
    for number in range(1, 5):
        game.guess(1, exact())
        assert not game.over
        assert game.start_next(number, make_location).number == number + 1
    game.guess(1, exact())
    assert game.over
    with pytest.raises(GameError):
        game.start_next(5, make_location)


def test_single_player_cannot_skip_a_round():
    game = SinglePlayerGame.start(1, make_location)
    with pytest.raises(GameError):
        game.start_next(1, make_location)


def test_single_player_next_round_is_safe_to_repeat():
    game = SinglePlayerGame.start(1, make_location)
    game.guess(1, exact())
    second = game.start_next(1, make_location)
    assert game.start_next(1, make_location) is second
    assert len(game.rounds) == 2


def test_single_player_timeout_closes_round_with_zero_points():
    game = SinglePlayerGame.start(1, make_location)
    expire(game.current)
    game.refresh()
    assert game.current.finished
    assert game.current.results() == {1: None}
    assert game.current.scores == {1: 0}
    with pytest.raises(GameError):
        game.guess(1, exact())
    assert game.start_next(1, make_location).number == 2


def test_guess_is_idempotent():
    game = SinglePlayerGame.start(1, make_location)
    first = game.guess(1, guess_at(0.0, 5.0))
    assert game.guess(1, guess_at(0.0, 99.0)) is first


def test_single_player_scores_each_round_and_totals_them():
    game = SinglePlayerGame.start(1, make_location)
    game.guess(1, exact())
    assert game.current.scores == {1: MAX_ROUND_SCORE}
    game.start_next(1, make_location)
    near_miss = guess_at(0.0, 10.0)
    game.guess(1, near_miss)
    expected = single_player_round_score(near_miss.distance_km)
    assert 0 < expected < MAX_ROUND_SCORE
    assert game.round_scores == [MAX_ROUND_SCORE, expected]
    assert game.total_score == MAX_ROUND_SCORE + expected


def test_single_player_unfinished_round_is_not_scored_yet():
    game = SinglePlayerGame.start(1, make_location)
    assert game.round_scores == [] and game.total_score == 0


# ---- lobby: when rounds end -------------------------------------------------
def test_lobby_round_ends_when_everyone_guessed():
    game = LobbyGame.start("lobby", {1, 2, 3}, make_location)
    game.guess(1, exact())
    game.guess(2, exact())
    assert not game.current.finished
    game.guess(3, exact())
    assert game.current.finished


def test_lobby_round_ends_on_timeout_with_missing_guesses():
    game = LobbyGame.start("lobby", {1, 2}, make_location)
    game.guess(1, exact())
    expire(game.current)
    game.refresh()
    assert game.current.finished
    results = game.current.results()
    assert results[1] is not None and results[2] is None
    with pytest.raises(GameError):
        game.guess(2, exact())


def test_lobby_needs_two_players_and_rejects_outsiders():
    with pytest.raises(GameError):
        LobbyGame.start("lobby", {1}, make_location)
    game = LobbyGame.start("lobby", {1, 2}, make_location)
    with pytest.raises(GameError):
        game.guess(99, exact())


def test_lobby_cannot_start_next_round_early():
    game = LobbyGame.start("lobby", {1, 2}, make_location)
    game.guess(1, exact())
    with pytest.raises(GameError):
        game.start_next(1, make_location)


# ---- lobby: points, elimination, winner -------------------------------------
def test_lobby_everyone_starts_with_full_points():
    game = LobbyGame.start("lobby", {1, 2, 3}, make_location)
    assert game.points == {1: STARTING_POINTS, 2: STARTING_POINTS, 3: STARTING_POINTS}


def test_closest_player_loses_nothing_others_lose_points():
    game = LobbyGame.start("lobby", {1, 2, 3}, make_location)
    finish_round(game, (1, guess_at(0.0, 1.0)), (2, guess_at(0.0, 5.0)), (3, guess_at(0.0, 10.0)))
    assert game.points[1] == STARTING_POINTS
    assert game.points[2] < STARTING_POINTS
    assert game.points[3] < game.points[2]
    assert game.current.penalties[1] == 0


def test_points_are_only_taken_once_per_round():
    game = LobbyGame.start("lobby", {1, 2}, make_location)
    finish_round(game, (1, exact()), (2, guess_at(0.0, 5.0)))
    after = dict(game.points)
    game.refresh()
    game.refresh()
    assert game.points == after


def test_missed_guess_costs_points_but_not_the_whole_stack():
    game = LobbyGame.start("lobby", {1, 2}, make_location)
    game.guess(1, exact())
    expire(game.current)
    game.refresh()
    assert game.points[1] == STARTING_POINTS
    assert 0 < game.points[2] < STARTING_POINTS


def test_penalties_grow_in_later_rounds():
    assert round_multiplier(10) > round_multiplier(1)
    game = LobbyGame.start("lobby", {1, 2}, make_location)
    lost = []
    for number in range(1, 8):
        before = game.points[2]
        finish_round(game, (1, exact()), (2, guess_at(0.0, 1.0)))
        lost.append(before - game.points[2])
        if game.over:
            break
        game.start_next(number, make_location)
    assert lost[0] == lost[1] == lost[2] == lost[3]   # flat early on
    assert lost[5] > lost[3]                          # then it hurts more


def test_player_at_zero_points_is_eliminated_and_skipped_next_round():
    game = LobbyGame.start("lobby", {1, 2, 3}, make_location)
    finish_round(game, (1, exact()), (2, far()), (3, guess_at(0.0, 1.0)))
    assert game.points[2] == 0
    assert game.eliminated == {2} and game.active == {1, 3}
    assert not game.over
    assert game.start_next(1, make_location).players == {1, 3}
    with pytest.raises(GameError):
        game.guess(2, exact())


def test_lobby_runs_until_one_player_remains():
    game = LobbyGame.start("lobby", {1, 2, 3}, make_location)
    finish_round(game, (1, exact()), (2, far()), (3, guess_at(0.0, 1.0)))
    assert not game.over
    game.start_next(1, make_location)
    finish_round(game, (1, exact()), (3, far()))
    assert game.over
    assert game.winner == 1
    assert game.eliminated == {2, 3}
    with pytest.raises(GameError):
        game.start_next(2, make_location)
    with pytest.raises(GameError):
        game.guess(1, exact())


def test_lobby_keeps_going_while_two_players_survive():
    game = LobbyGame.start("lobby", {1, 2}, make_location)
    for number in range(1, 4):
        finish_round(game, (1, exact()), (2, guess_at(0.0, 0.5)))
        assert not game.over
        game.start_next(number, make_location)


def test_nobody_guessing_cannot_wipe_out_every_player():
    game = LobbyGame.start("lobby", {1, 2}, make_location)
    game.points = {1: 100, 2: 100}   # small enough that the no-guess penalty would kill both
    expire(game.current)
    game.refresh()
    assert game.points == {1: 100, 2: 100}
    assert game.current.penalties == {1: 0, 2: 0}
    assert not game.over


def test_nobody_guessing_early_costs_everyone_equally():
    game = LobbyGame.start("lobby", {1, 2}, make_location)
    expire(game.current)
    game.refresh()
    assert game.points[1] == game.points[2] < STARTING_POINTS
