"""Tests for app/modules/rounds/service.py (pure logic, no server needed)."""
from types import SimpleNamespace

import pytest

from app.modules.rounds import service
from app.modules.rounds.service import (
    GameError, LobbyGame, PlayerGuess, SinglePlayerGame, round_multiplier,
)


@pytest.fixture(autouse=True)
def reset_hook():
    yield
    service.round_end_hook = service.no_elimination


def make_location(previous=None):
    make_location.count += 1
    return SimpleNamespace(pano_id=f"pano{make_location.count}", lat=0, lng=0)


make_location.count = 0


def guess(distance=10.0):
    return PlayerGuess(lat=0, lng=0, distance_km=distance)


def expire(game_round):
    game_round.started_at -= 10_000


def test_multiplier_is_flat_then_grows():
    assert [round_multiplier(n) for n in (1, 2, 3)] == [1.0, 1.0, 1.0]
    assert round_multiplier(4) == 1.5
    assert round_multiplier(5) == 2.0
    assert round_multiplier(50) > round_multiplier(49)


def test_single_player_has_exactly_five_rounds():
    game = SinglePlayerGame.start(1, make_location)
    for number in range(1, 5):
        game.current.submit(1, guess())
        assert not game.over
        assert game.start_next(number, make_location).number == number + 1
    game.current.submit(1, guess())
    assert game.over
    with pytest.raises(GameError):
        game.start_next(5, make_location)


def test_single_player_cannot_skip_a_round():
    game = SinglePlayerGame.start(1, make_location)
    with pytest.raises(GameError):
        game.start_next(1, make_location)


def test_single_player_next_round_is_safe_to_repeat():
    game = SinglePlayerGame.start(1, make_location)
    game.current.submit(1, guess())
    second = game.start_next(1, make_location)
    assert game.start_next(1, make_location) is second
    assert len(game.rounds) == 2


def test_single_player_timeout_closes_round_without_guess():
    game = SinglePlayerGame.start(1, make_location)
    expire(game.current)
    game.refresh()
    assert game.current.finished
    assert game.current.results() == {1: None}
    with pytest.raises(GameError):
        game.current.submit(1, guess())
    assert game.start_next(1, make_location).number == 2


def test_guess_is_idempotent():
    game = SinglePlayerGame.start(1, make_location)
    first = game.current.submit(1, guess(5))
    assert game.current.submit(1, guess(99)) is first


def test_lobby_round_ends_when_everyone_guessed():
    game = LobbyGame.start("lobby", {1, 2, 3}, make_location)
    game.guess(1, guess())
    game.guess(2, guess())
    assert not game.current.finished
    game.guess(3, guess())
    assert game.current.finished


def test_lobby_round_ends_on_timeout_with_missing_guesses():
    game = LobbyGame.start("lobby", {1, 2}, make_location)
    game.guess(1, guess())
    expire(game.current)
    game.refresh()
    assert game.current.finished
    results = game.current.results()
    assert results[1] is not None and results[2] is None
    with pytest.raises(GameError):
        game.guess(2, guess())


def test_lobby_needs_two_players_and_rejects_outsiders():
    with pytest.raises(GameError):
        LobbyGame.start("lobby", {1}, make_location)
    game = LobbyGame.start("lobby", {1, 2}, make_location)
    with pytest.raises(GameError):
        game.guess(99, guess())


def test_lobby_cannot_start_next_round_early():
    game = LobbyGame.start("lobby", {1, 2}, make_location)
    game.guess(1, guess())
    with pytest.raises(GameError):
        game.start_next(1, make_location)


def test_default_hook_never_eliminates():
    game = LobbyGame.start("lobby", {1, 2}, make_location)
    for number in range(1, 8):
        game.guess(1, guess())
        game.guess(2, guess())
        game.start_next(number, make_location)
    assert not game.over and game.active == {1, 2}


def test_lobby_runs_until_one_player_remains():
    # Stand-in for the scoring teammate: eliminate the lowest id every round.
    service.round_end_hook = lambda g, r: {min(g.active)}
    game = LobbyGame.start("lobby", {1, 2, 3, 4}, make_location)
    rounds_played = 0
    while not game.over:
        rounds_played += 1
        for pid in sorted(game.active):
            game.guess(pid, guess())
        if not game.over:
            game.start_next(rounds_played, make_location)
    assert rounds_played == 3
    assert game.winner == 4
    assert game.eliminated == {1, 2, 3}
    with pytest.raises(GameError):
        game.start_next(3, make_location)


def test_end_of_round_hook_runs_once_per_round():
    calls = []
    service.round_end_hook = lambda g, r: calls.append(r.number) or set()
    game = LobbyGame.start("lobby", {1, 2}, make_location)
    game.guess(1, guess())
    game.guess(2, guess())
    game.refresh()
    game.refresh()
    assert calls == [1]


def test_cannot_eliminate_everyone():
    game = LobbyGame.start("lobby", {1, 2}, make_location)
    with pytest.raises(ValueError):
        game.eliminate({1, 2})


def test_eliminated_player_not_in_next_round():
    service.round_end_hook = lambda g, r: {2}
    game = LobbyGame.start("lobby", {1, 2, 3}, make_location)
    for pid in (1, 2, 3):
        game.guess(pid, guess())
    nxt = game.start_next(1, make_location)
    assert nxt.players == {1, 3}
