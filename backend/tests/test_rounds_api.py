"""Endpoint tests for /games (app/modules/rounds/router.py), with focus on the server-side round timer."""
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.main import app
from app.modules.auth.deps import get_current_user
from app.modules.lobby import router as lobby_router
from app.modules.lobby.service import LobbyManager
from app.modules.location.service import Location
from app.modules.rounds import router as rounds_router
from app.scoring import STARTING_POINTS, single_player_round_score

# The true location in every test. Its coordinates are distinctive so we can check they never leak early.
TRUE_LAT, TRUE_LNG = 12.5, 34.5
NEAR = {"lat": TRUE_LAT, "lng": TRUE_LNG + 1}          # about 108 km away
EXACT = {"lat": TRUE_LAT, "lng": TRUE_LNG}
OPPOSITE_SIDE = {"lat": -TRUE_LAT, "lng": TRUE_LNG - 180}  # about 20,000 km away: wipes out 10,000 points


@pytest.fixture(autouse=True)
def fresh_games(monkeypatch):
    rounds_router.single_games.clear()
    rounds_router.lobby_games.clear()
    monkeypatch.setattr(lobby_router, "lobby_manager", LobbyManager())  # rooms must not leak between tests
    counter = iter(range(1, 1000))
    monkeypatch.setattr(
        rounds_router, "generate_location",
        lambda exclude=None: Location(pano_id=f"pano{next(counter)}", lat=TRUE_LAT, lng=TRUE_LNG),
    )
    yield
    rounds_router.single_games.clear()
    rounds_router.lobby_games.clear()


def authenticate(user_id=1):
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=user_id, username=f"player{user_id}")


def expire_single(user_id=1):
    """Pretend the round's 60 seconds are up."""
    rounds_router.single_games[user_id].current.started_at -= 10_000


def expire_lobby(lobby_id):
    rounds_router.lobby_games[UUID(lobby_id)].current.started_at -= 10_000


def start_single(client):
    response = client.post("/games/single")
    assert response.status_code == 200
    return response.json()


def make_lobby(client, host=1, guests=(2,)):
    authenticate(host)
    created = client.post("/lobbies/createLobby", json={"name": "Test lobby"})
    assert created.status_code == 201
    lobby_id = created.json()["id"]
    code = lobby_router.lobby_manager.lobbies[UUID(lobby_id)].code
    for guest in guests:
        authenticate(guest)
        assert client.post(f"/lobbies/{code}/join").status_code == 200
    authenticate(host)
    return lobby_id


def start_lobby(client, lobby_id, host=1):
    authenticate(host)
    response = client.post(f"/games/lobby/{lobby_id}/start")
    assert response.status_code == 200
    return response.json()


def guess_as(client, lobby_id, user_id, guess):
    authenticate(user_id)
    return client.post(f"/games/lobby/{lobby_id}/guess", json=guess)


# ---- single player: the timer -----------------------------------------------
def test_new_round_has_a_running_timer_and_hides_the_answer(client):
    authenticate()
    response = client.post("/games/single")
    game = response.json()
    current = game["current_round"]
    assert current["number"] == 1 and current["total_rounds"] == 5
    assert 0 < current["seconds_left"] <= 60
    assert current["finished"] is False and current["pano_id"] == "pano1"
    assert current["answer"] is None and current["results"] is None
    assert str(TRUE_LAT) not in response.text and str(TRUE_LNG) not in response.text


def test_timer_running_out_ends_the_round_with_no_guess(client):
    authenticate()
    start_single(client)
    expire_single()
    current = client.get("/games/single").json()["current_round"]
    assert current["finished"] is True
    assert current["seconds_left"] == 0
    assert current["answer"] == {"lat": TRUE_LAT, "lng": TRUE_LNG}
    (result,) = current["results"].values()
    assert result["guessed"] is False and result["score"] == 0 and result["distance_km"] is None


def test_guess_after_the_timer_is_refused(client):
    authenticate()
    start_single(client)
    expire_single()
    late = client.post("/games/single/guess", json=NEAR)
    assert late.status_code == 409
    assert late.json()["detail"] == "Time is up for this round."
    (result,) = client.get("/games/single").json()["current_round"]["results"].values()
    assert result["guessed"] is False


def test_timed_out_round_scores_zero_and_next_round_starts(client):
    authenticate()
    start_single(client)
    expire_single()
    game = client.get("/games/single").json()
    assert game["round_scores"] == [0] and game["total_score"] == 0
    second = client.post("/games/single/next", json={"previous_round": 1}).json()
    assert second["current_round"]["number"] == 2
    assert second["current_round"]["finished"] is False
    assert second["current_round"]["seconds_left"] > 0


def test_guess_in_time_ends_round_reveals_answer_and_scores(client):
    authenticate()
    start_single(client)
    game = client.post("/games/single/guess", json=NEAR).json()
    current = game["current_round"]
    assert current["finished"] is True
    assert current["answer"] == {"lat": TRUE_LAT, "lng": TRUE_LNG}
    (result,) = current["results"].values()
    assert result["guessed"] is True
    assert result["score"] == single_player_round_score(result["distance_km"])
    assert game["round_scores"] == [result["score"]] and game["total_score"] == result["score"]


def test_retrying_a_guess_does_not_change_the_result(client):
    authenticate()
    start_single(client)
    first = client.post("/games/single/guess", json=NEAR).json()
    again = client.post("/games/single/guess", json=OPPOSITE_SIDE).json()
    assert again["current_round"]["results"] == first["current_round"]["results"]


# ---- single player: rounds --------------------------------------------------
def test_starting_again_returns_the_game_in_progress(client):
    authenticate()
    first = start_single(client)
    again = start_single(client)
    assert again["current_round"]["pano_id"] == first["current_round"]["pano_id"]


def test_next_round_is_refused_until_the_round_is_over(client):
    authenticate()
    start_single(client)
    assert client.post("/games/single/next", json={"previous_round": 1}).status_code == 409


def test_game_lasts_exactly_five_rounds(client):
    authenticate()
    start_single(client)
    for number in range(1, 6):
        game = client.post("/games/single/guess", json=EXACT).json()
        assert game["current_round"]["number"] == number
        assert game["over"] is (number == 5)
        if number < 5:
            assert client.post("/games/single/next", json={"previous_round": number}).status_code == 200
    assert len(game["round_scores"]) == 5
    assert client.post("/games/single/next", json={"previous_round": 5}).status_code == 409
    fresh = start_single(client)  # a finished game is replaced by a new one
    assert fresh["current_round"]["number"] == 1 and fresh["over"] is False


def test_each_player_has_their_own_game(client):
    authenticate(1)
    start_single(client)
    client.post("/games/single/guess", json=EXACT)
    authenticate(2)
    other = start_single(client)
    assert other["current_round"]["finished"] is False
    assert other["total_score"] == 0


@pytest.mark.parametrize("body", [{"lat": 100, "lng": 0}, {"lat": 0, "lng": 181}, {"lat": 0, "lng": 0, "answer": 1}])
def test_invalid_guesses_are_rejected(client, body):
    authenticate()
    start_single(client)
    assert client.post("/games/single/guess", json=body).status_code == 422


def test_no_game_in_progress_returns_404(client):
    authenticate()
    assert client.get("/games/single").status_code == 404


@pytest.mark.parametrize("method,path,body", [
    ("post", "/games/single", None),
    ("get", "/games/single", None),
    ("post", "/games/single/guess", {"lat": 0, "lng": 0}),
    ("post", "/games/single/next", {"previous_round": 1}),
    ("post", f"/games/lobby/{uuid4()}/start", None),
    ("get", f"/games/lobby/{uuid4()}", None),
    ("post", f"/games/lobby/{uuid4()}/guess", {"lat": 0, "lng": 0}),
    ("post", f"/games/lobby/{uuid4()}/next", {"previous_round": 1}),
])
def test_game_endpoints_require_login(client, method, path, body):
    kwargs = {"json": body} if body is not None else {}
    assert getattr(client, method)(path, **kwargs).status_code == 401


# ---- lobby ------------------------------------------------------------------
def test_only_the_host_can_start_and_two_players_are_needed(client):
    lobby_id = make_lobby(client, guests=())
    assert client.post(f"/games/lobby/{lobby_id}/start").status_code == 409  # alone in the lobby
    lobby_id = make_lobby(client, host=3, guests=(4,))
    authenticate(4)
    assert client.post(f"/games/lobby/{lobby_id}/start").status_code == 403
    authenticate(3)
    assert client.post(f"/games/lobby/{uuid4()}/start").status_code == 404


def test_lobby_round_waits_for_everyone_then_applies_points(client):
    lobby_id = make_lobby(client)
    game = start_lobby(client, lobby_id)
    assert game["mode"] == "lobby" and game["current_round"]["total_rounds"] is None
    assert game["points"] == {"1": STARTING_POINTS, "2": STARTING_POINTS}

    first = guess_as(client, lobby_id, 1, EXACT).json()["current_round"]
    assert first["finished"] is False and first["submitted"] == [1]
    assert first["answer"] is None and first["results"] is None

    game = guess_as(client, lobby_id, 2, NEAR).json()
    current = game["current_round"]
    assert current["finished"] is True and current["submitted"] == [1, 2]
    assert current["answer"] == {"lat": TRUE_LAT, "lng": TRUE_LNG}
    assert current["results"]["1"]["penalty"] == 0
    assert current["results"]["2"]["penalty"] > 0
    assert game["points"]["1"] == STARTING_POINTS
    assert game["points"]["2"] < STARTING_POINTS and game["over"] is False


def test_lobby_timer_ends_the_round_and_penalises_players_who_did_not_guess(client):
    lobby_id = make_lobby(client)
    start_lobby(client, lobby_id)
    guess_as(client, lobby_id, 1, EXACT)
    expire_lobby(lobby_id)
    authenticate(1)
    game = client.get(f"/games/lobby/{lobby_id}").json()
    current = game["current_round"]
    assert current["finished"] is True and current["seconds_left"] == 0
    assert current["results"]["1"]["guessed"] is True and current["results"]["1"]["penalty"] == 0
    assert current["results"]["2"]["guessed"] is False and current["results"]["2"]["penalty"] > 0
    assert game["points"]["2"] < game["points"]["1"] == STARTING_POINTS


def test_lobby_guess_after_the_timer_is_refused(client):
    lobby_id = make_lobby(client)
    start_lobby(client, lobby_id)
    expire_lobby(lobby_id)
    late = guess_as(client, lobby_id, 1, EXACT)
    assert late.status_code == 409 and late.json()["detail"] == "Time is up for this round."


def test_lobby_next_round_needs_everyone_done_and_is_safe_to_repeat(client):
    lobby_id = make_lobby(client)
    start_lobby(client, lobby_id)
    guess_as(client, lobby_id, 1, EXACT)
    assert client.post(f"/games/lobby/{lobby_id}/next", json={"previous_round": 1}).status_code == 409
    guess_as(client, lobby_id, 2, NEAR)
    authenticate(2)
    second = client.post(f"/games/lobby/{lobby_id}/next", json={"previous_round": 1}).json()
    assert second["current_round"]["number"] == 2 and second["current_round"]["finished"] is False
    authenticate(1)
    again = client.post(f"/games/lobby/{lobby_id}/next", json={"previous_round": 1}).json()
    assert again["current_round"]["pano_id"] == second["current_round"]["pano_id"]


def test_player_at_zero_points_is_out_and_last_player_wins(client):
    lobby_id = make_lobby(client)
    start_lobby(client, lobby_id)
    guess_as(client, lobby_id, 1, EXACT)
    game = guess_as(client, lobby_id, 2, OPPOSITE_SIDE).json()
    assert game["points"]["2"] == 0
    assert game["eliminated_players"] == [2] and game["active_players"] == [1]
    assert game["over"] is True and game["winner"] == 1
    authenticate(1)
    assert client.post(f"/games/lobby/{lobby_id}/next", json={"previous_round": 1}).status_code == 409
    assert guess_as(client, lobby_id, 1, EXACT).status_code == 409


def test_outsiders_cannot_see_or_join_a_lobby_game(client):
    lobby_id = make_lobby(client)
    start_lobby(client, lobby_id)
    authenticate(99)
    assert client.get(f"/games/lobby/{lobby_id}").status_code == 403
    assert client.post(f"/games/lobby/{lobby_id}/guess", json=EXACT).status_code == 403


def test_game_in_a_lobby_that_never_started_returns_404(client):
    lobby_id = make_lobby(client)
    assert client.get(f"/games/lobby/{lobby_id}").status_code == 404
