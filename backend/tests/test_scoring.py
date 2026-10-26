import math

from app.modules.lobby.service import Lobby, Player
from app.scoring import (
    MAX_ROUND_SCORE, STARTING_POINTS, apply_penalties, haversine_distance,
    is_lobby_game_over, lobby_round_penalties, lobby_winner, new_lobby_points,
    players_alive, round_multiplier, single_player_round_score, single_player_total,
)

TRUE = (0.0, 0.0)


def test_same_points_returns_zero():
    assert haversine_distance(40.7128, -74.0060, 40.7128, -74.0060) == 0

def test_known_distance_nyc_to_london():
    distance = haversine_distance(40.7128, -74.0060, 51.5074, -0.1278)
    assert math.isclose(distance, 5570.8, rel_tol=0.02)


# ---- single player ----
def test_exact_guess_gets_max_score():
    assert single_player_round_score(0) == MAX_ROUND_SCORE

def test_score_goes_down_as_distance_goes_up():
    scores = [single_player_round_score(d) for d in (0, 100, 1000, 5000, 15000)]
    assert scores == sorted(scores, reverse=True)
    assert scores[-1] < 5

def test_single_player_total_adds_rounds():
    assert single_player_total([5000, 4000, 3000, 2000, 1000]) == 15000


# ---- lobby ----
def test_new_lobby_points_matches_lobby_players():
    lobby = Lobby()
    lobby.initialize_lobby(Player(7))
    lobby.add_player(Player(9))
    assert new_lobby_points(lobby.players) == {7: STARTING_POINTS, 9: STARTING_POINTS}

def test_closest_player_loses_nothing_and_others_lose_points():
    guesses = {1: (0.0, 1.0), 2: (0.0, 5.0), 3: (0.0, 10.0)}
    penalties = lobby_round_penalties(guesses, *TRUE)
    assert penalties[1] == 0
    assert 0 < penalties[2] < penalties[3]

def test_penalty_is_distance_from_closest_guess_not_from_truth():
    guesses = {1: (0.0, 1.0), 2: (0.0, 2.0)}
    expected = round(haversine_distance(0.0, 2.0, 0.0, 1.0))
    assert lobby_round_penalties(guesses, *TRUE)[2] == expected

def test_missing_guess_gets_penalty_and_cannot_be_closest():
    penalties = lobby_round_penalties({1: (0.0, 1.0), 2: None}, *TRUE)
    assert penalties[1] == 0
    assert penalties[2] > 0

def test_nobody_guessed_everyone_gets_penalty():
    penalties = lobby_round_penalties({1: None, 2: None}, *TRUE)
    assert penalties[1] > 0 and penalties[1] == penalties[2]

def test_multiplier_grows_after_start_round():
    assert round_multiplier(1) == 1.0
    assert round_multiplier(10) > round_multiplier(6) > round_multiplier(5) >= 1.0
    guesses = {1: (0.0, 1.0), 2: (0.0, 5.0)}
    early = lobby_round_penalties(guesses, *TRUE, round_number=1)[2]
    late = lobby_round_penalties(guesses, *TRUE, round_number=10)[2]
    assert late > early

def test_apply_penalties_never_goes_below_zero():
    assert apply_penalties({1: 100, 2: 50}, {1: 30, 2: 500}) == {1: 70, 2: 0}

def test_game_ends_when_one_player_left_and_winner_is_found():
    points = {1: 4000, 2: 0, 3: 0}
    assert players_alive(points) == [1]
    assert is_lobby_game_over(points)
    assert lobby_winner(points) == 1

def test_game_continues_with_two_alive_and_tie_has_no_winner():
    assert not is_lobby_game_over({1: 10, 2: 10})
    assert lobby_winner({1: 10, 2: 10}) is None
    assert lobby_winner({1: 0, 2: 0}) is None