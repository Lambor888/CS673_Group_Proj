from types import SimpleNamespace

import pytest

from app.modules.lobby import router as lobby_router
from app.modules.lobby.service import ConnectionManager, LobbyManager
from app.modules.multiplayer_loop import router as multi_router
from app.scoring import STARTING_POINTS

from tests.test_lobby_api import create_lobby, join, login_user
from tests.test_lobby_ws import connect, receive_until


@pytest.fixture(autouse=True)
def fresh_state(monkeypatch, db_session):
    manager = LobbyManager()
    monkeypatch.setattr(lobby_router, "lobby_manager", manager)
    monkeypatch.setattr(lobby_router, "connection_manager", ConnectionManager())
    monkeypatch.setattr(multi_router, "lobby_manager", manager)
    monkeypatch.setattr(multi_router, "lobby_games", {})
    monkeypatch.setattr(multi_router, "open_session", lambda: db_session)
    counter = iter(range(1, 1000))
    monkeypatch.setattr(
        multi_router, "new_location",
        lambda previous=None: SimpleNamespace(pano_id=f"pano-{next(counter)}", lat=0.0, lng=0.0),
    )


@pytest.fixture
def live(client):
    with client:
        yield client


def lobby_of(client, count):
    users = [login_user(client, f"player{i}") for i in range(count)]
    lobby = create_lobby(client, users[0][1])
    for _, headers in users[1:]:
        assert join(client, headers, lobby).status_code == 200
    return lobby, users


def history(client, headers):
    return client.get("/profile/history", headers=headers).json()


def start(client, lobby, headers):
    return client.post(f"/games/lobby/{lobby['id']}/start", headers=headers)


# Game starting 
def test_host_starts_game_and_everyone_is_told_to_open_it(live):
    lobby, ((host_id, host), (guest_id, guest)) = lobby_of(live, 2)
    with connect(live, host, lobby["id"]) as host_ws, connect(live, guest, lobby["id"]) as guest_ws:
        assert start(live, lobby, host).status_code == 200
        assert live.post(f"/lobbies/{lobby['id']}/start", headers=host).status_code == 200
        assert receive_until(host_ws, "game_started")
        assert receive_until(guest_ws, "game_started")
    for headers in (host, guest):
        state = live.get(f"/games/lobby/{lobby['id']}", headers=headers).json()
        assert state["current_round"]["number"] == 1
        assert state["current_round"]["pano_id"] == "pano-1"
        assert state["current_round"]["answer"] is None 
        assert state["points"] == {str(host_id): STARTING_POINTS, str(guest_id): STARTING_POINTS}
        assert state["final_results"] is None


def test_only_the_host_can_start_and_one_player_cannot(live):
    lobby, ((_, host), (_, guest)) = lobby_of(live, 2)
    assert start(live, lobby, guest).status_code == 403
    _, solo = login_user(live, "solo")
    alone = create_lobby(live, solo, "Alone")
    assert start(live, alone, solo).status_code == 409


def test_outsiders_cannot_see_or_join_the_game(live):
    lobby, ((_, host), _) = lobby_of(live, 2)
    start(live, lobby, host)
    _, outsider = login_user(live, "outsider")
    assert live.get(f"/games/lobby/{lobby['id']}", headers=outsider).status_code == 403
    assert live.post(f"/games/lobby/{lobby['id']}/guess", headers=outsider, json={"lat": 0, "lng": 0}).status_code == 403


#rounds and the countdown 
def test_first_guess_starts_a_ten_second_countdown_for_the_others(live):
    lobby, ((host_id, host), (guest_id, guest)) = lobby_of(live, 2)
    start(live, lobby, host)
    url = f"/games/lobby/{lobby['id']}"
    before = live.get(url, headers=guest).json()["current_round"]["seconds_left"]
    assert before > 50
    first = live.post(f"{url}/guess", headers=host, json={"lat": 0, "lng": 1}).json()["current_round"]
    assert first["seconds_left"] <= 10 and not first["finished"]
    assert live.get(url, headers=guest).json()["current_round"]["seconds_left"] <= 10


def test_two_players_play_a_round_and_start_the_next(live):
    lobby, ((host_id, host), (guest_id, guest)) = lobby_of(live, 2)
    url = f"/games/lobby/{lobby['id']}"
    start(live, lobby, host)
    live.post(f"{url}/guess", headers=host, json={"lat": 0, "lng": 1})
    done = live.post(f"{url}/guess", headers=guest, json={"lat": 0, "lng": 5}).json()
    one = done["current_round"]
    assert one["finished"] and one["answer"] == {"lat": 0.0, "lng": 0.0}
    assert one["results"][str(host_id)]["penalty"] == 0
    assert one["results"][str(guest_id)]["penalty"] > 0
    assert done["points"][str(host_id)] == STARTING_POINTS
    assert done["points"][str(guest_id)] < STARTING_POINTS
    assert not done["over"]

    nxt = live.post(f"{url}/next", headers=guest, json={"previous_round": 1}).json()
    assert nxt["current_round"]["number"] == 2 and nxt["current_round"]["pano_id"] == "pano-2"
    again = live.post(f"{url}/next", headers=host, json={"previous_round": 1}).json()
    assert again["current_round"]["number"] == 2  


def test_there_is_no_round_limit(live):
    lobby, ((_, host), (_, guest)) = lobby_of(live, 2)
    url = f"/games/lobby/{lobby['id']}"
    start(live, lobby, host)
    for number in range(1, 9):                                
        live.post(f"{url}/guess", headers=host, json={"lat": 0, "lng": 1})
        state = live.post(f"{url}/guess", headers=guest, json={"lat": 0, "lng": 1.01}).json()
        assert state["current_round"]["number"] == number and not state["over"]
        live.post(f"{url}/next", headers=host, json={"previous_round": number})
    assert history(live, host) == []                          


# the game ends when one player is left, and the results saved
def test_last_player_standing_wins_and_results_are_sent_and_saved(live):
    lobby, ((host_id, host), (guest_id, guest)) = lobby_of(live, 2)
    url = f"/games/lobby/{lobby['id']}"
    start(live, lobby, host)
    multi_router.lobby_games[__import__("uuid").UUID(lobby["id"])].points[guest_id] = 500
    live.post(f"{url}/guess", headers=host, json={"lat": 0, "lng": 1})
    done = live.post(f"{url}/guess", headers=guest, json={"lat": 0, "lng": 50}).json() 

    assert done["over"] and done["winner"] == host_id
    results = done["final_results"]
    assert [(r["rank"], r["player_id"], r["username"]) for r in results] == [
        (1, host_id, "player0"), (2, guest_id, "player1")]
    assert results[0]["final_score"] == STARTING_POINTS and results[1]["final_score"] == 0

    mine = history(live, host)
    assert len(mine) == 1
    assert (mine[0]["mode"], mine[0]["placement"], mine[0]["won"], mine[0]["players"]) == ("lobby", 1, True, 2)
    assert mine[0]["final_score"] == STARTING_POINTS and mine[0]["rounds_played"] == 1
    theirs = history(live, guest)
    assert (theirs[0]["placement"], theirs[0]["won"], theirs[0]["final_score"]) == (2, False, 0)

    live.get(url, headers=host)
    assert len(history(live, host)) == 1 and len(history(live, guest)) == 1
    assert live.post(f"{url}/next", headers=host, json={"previous_round": 1}).status_code == 409


def test_game_ends_when_the_other_player_leaves(live):
    lobby, ((host_id, host), (guest_id, guest)) = lobby_of(live, 2)
    url = f"/games/lobby/{lobby['id']}"
    start(live, lobby, host)
    assert live.post(f"/lobbies/{lobby['id']}/leave", headers=guest).status_code == 204
    state = live.get(url, headers=host).json()
    assert state["over"] and state["winner"] == host_id
    assert [r["rank"] for r in state["final_results"]] == [1, 2]
    assert history(live, host)[0]["won"] is True
    assert history(live, guest)[0]["placement"] == 2 

def test_game_goes_on_while_two_or_more_players_remain(live):
    lobby, ((host_id, host), (_, guest), (third_id, third)) = lobby_of(live, 3)
    url = f"/games/lobby/{lobby['id']}"
    start(live, lobby, host)
    live.post(f"{url}/guess", headers=host, json={"lat": 0, "lng": 1})
    assert live.post(f"/lobbies/{lobby['id']}/leave", headers=third).status_code == 204
    state = live.get(url, headers=host).json()
    assert state["eliminated_players"] == [third_id] and not state["over"]
    done = live.post(f"{url}/guess", headers=guest, json={"lat": 0, "lng": 5}).json()
    assert done["current_round"]["finished"]              
    assert history(live, host) == []


def test_host_leaving_closes_the_lobby_and_the_unfinished_game_is_not_saved(live):
    lobby, ((_, host), (_, guest)) = lobby_of(live, 2)
    start(live, lobby, host)
    live.post(f"/lobbies/{lobby['id']}/leave", headers=host)
    assert live.get(f"/games/lobby/{lobby['id']}", headers=guest).status_code == 404
    assert history(live, host) == [] and history(live, guest) == []
