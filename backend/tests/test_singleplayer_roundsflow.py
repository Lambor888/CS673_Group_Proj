"""Single player on the round system: 5 rounds, total score, timer, and profile stats."""
from types import SimpleNamespace

import pytest

from app.modules.rounds import router as rounds_router
from app.scoring import MAX_ROUND_SCORE, SINGLE_PLAYER_ROUNDS

from tests.test_lobby_api import login_user


@pytest.fixture(autouse=True)
def fresh_state(monkeypatch):
    monkeypatch.setattr(rounds_router, "single_games", {})
    counter = iter(range(1, 100))
    monkeypatch.setattr(
        rounds_router, "new_location",
        lambda previous=None: SimpleNamespace(pano_id=f"pano-{next(counter)}", lat=0.0, lng=0.0),
    )


def stats(client, headers):
    return client.get("/profile/stats", headers=headers).json()


def test_five_rounds_then_game_over_and_a_new_game(client):
    user_id, headers = login_user(client, "solo")
    game = client.post("/games/single", headers=headers).json()
    assert game["current_round"]["number"] == 1
    assert game["current_round"]["total_rounds"] == SINGLE_PLAYER_ROUNDS
    assert not game["over"] and game["total_score"] == 0

    # Starting again while a game is running just returns it (a page reload keeps the round).
    assert client.post("/games/single", headers=headers).json()["current_round"]["pano_id"] == "pano-1"

    for number in range(1, SINGLE_PLAYER_ROUNDS + 1):
        state = client.post("/games/single/guess", headers=headers, json={"lat": 0, "lng": 0}).json()
        assert state["current_round"]["finished"]
        assert state["current_round"]["answer"] == {"lat": 0.0, "lng": 0.0}
        assert state["round_scores"] == [MAX_ROUND_SCORE] * number
        if number < SINGLE_PLAYER_ROUNDS:
            assert not state["over"]
            nxt = client.post("/games/single/next", headers=headers, json={"previous_round": number}).json()
            assert nxt["current_round"]["number"] == number + 1

    assert state["over"] and state["total_score"] == MAX_ROUND_SCORE * SINGLE_PLAYER_ROUNDS
    assert client.post("/games/single/next", headers=headers, json={"previous_round": 5}).status_code == 409
    client.get("/games/single", headers=headers)
    history = client.get("/profile/history", headers=headers).json()
    assert len(history) == 1
    assert history[0]["final_score"] == MAX_ROUND_SCORE * SINGLE_PLAYER_ROUNDS
    assert history[0]["rounds_played"] == SINGLE_PLAYER_ROUNDS

    fresh = client.post("/games/single", headers=headers).json()     # "Play again"
    assert fresh["current_round"]["number"] == 1 and fresh["total_score"] == 0 and not fresh["over"]
    assert len(client.get("/profile/history", headers=headers).json()) == 1


def test_delayed_guess_does_not_submit_to_the_next_round(client):
    _, headers = login_user(client, "delayed")
    first = client.post("/games/single", headers=headers).json()["current_round"]
    body = {"lat": 0, "lng": 0, "round_id": first["round_id"]}
    assert client.post("/games/single/guess", headers=headers, json=body).status_code == 200
    client.post("/games/single/next", headers=headers, json={"previous_round": 1})
    assert client.post("/games/single/guess", headers=headers, json=body).status_code == 409
    current = client.get("/games/single", headers=headers).json()["current_round"]
    assert current["number"] == 2 and current["submitted"] == []


def test_guesses_are_saved_to_profile_stats_once(client):
    _, headers = login_user(client, "stats")
    client.post("/games/single", headers=headers)
    client.post("/games/single/guess", headers=headers, json={"lat": 0, "lng": 1})
    client.post("/games/single/guess", headers=headers, json={"lat": 0, "lng": 1})   # retry
    saved = stats(client, headers)
    assert saved["rounds_played"] == 1                       # the retry did not count twice
    assert saved["best_distance_km"] == pytest.approx(111.195, abs=0.01)
    assert saved["total_score"] > 0


def test_round_that_times_out_scores_zero_and_is_not_saved(client):
    user_id, headers = login_user(client, "slow")
    client.post("/games/single", headers=headers)
    rounds_router.single_games[user_id].current.started_at -= 1000     # the 60 seconds pass
    state = client.get("/games/single", headers=headers).json()
    assert state["current_round"]["finished"] and state["total_score"] == 0
    assert state["current_round"]["results"][str(user_id)]["guessed"] is False
    assert client.post("/games/single/guess", headers=headers, json={"lat": 0, "lng": 0}).status_code == 409
    assert stats(client, headers)["rounds_played"] == 0
