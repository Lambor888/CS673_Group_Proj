from uuid import uuid4

import pytest

from app.modules.lobby import router as lobby_router
from app.modules.lobby.service import LobbyManager


@pytest.fixture(autouse=True)
def fresh_lobbies(monkeypatch):
    # The app's in-memory rooms must not leak between tests.
    monkeypatch.setattr(lobby_router, "lobby_manager", LobbyManager())


def login_user(client, username="alice"):
    credentials = {"username": username, "password": "password123"}
    registered = client.post("/auth/register", json=credentials)
    assert registered.status_code == 201
    logged_in = client.post("/auth/login", data=credentials)
    assert logged_in.status_code == 200
    headers = {"Authorization": f"Bearer {logged_in.json()['access_token']}"}
    return registered.json()["id"], headers


def create_lobby(client, headers, name="Test lobby"):
    response = client.post("/lobbies/createLobby", headers=headers, json={"name": name})
    assert response.status_code == 201
    return response.json()


def join(client, headers, lobby):
    # Rooms are joined by their 6-character code, not by id.
    return client.post(f"/lobbies/{lobby['code']}/join", headers=headers)


def get(client, headers, lobby):
    return client.get(f"/lobbies/{lobby['id']}", headers=headers)


def leave(client, headers, lobby):
    return client.post(f"/lobbies/{lobby['id']}/leave", headers=headers)


def test_create_and_get_lobby(client):
    host_id, headers = login_user(client)
    lobby = create_lobby(client, headers, "  Friends  ")
    assert lobby == {
        "id": lobby["id"],
        "name": "Friends",
        "player_ids": {str(host_id): {"id": host_id, "name": "alice"}},
        "host_id": host_id,
        "num_players": 1,
        "max_players": 5,
        "flag": False,
        "code": lobby["code"],
    }
    assert len(lobby["code"]) == 6 and lobby["code"].isalnum() and lobby["code"].isupper()
    response = get(client, headers, lobby)
    assert response.status_code == 200
    assert response.json() == lobby


@pytest.mark.parametrize("name", ["", "   ", "\t\n", "x" * 21])
def test_invalid_lobby_name(client, name):
    _, headers = login_user(client)
    response = client.post("/lobbies/createLobby", headers=headers, json={"name": name})
    assert response.status_code == 422
    assert lobby_router.lobby_manager.get_all_lobbies() == []


def test_join_leave_and_repeat_requests(client):
    host_id, host = login_user(client)
    guest_id, guest = login_user(client, "guest")
    lobby = create_lobby(client, host)

    joined = join(client, guest, lobby)
    assert joined.status_code == 200
    assert joined.json()["num_players"] == 2
    assert joined.json()["player_ids"] == {
        str(host_id): {"id": host_id, "name": "alice"},
        str(guest_id): {"id": guest_id, "name": "guest"},
    }
    assert joined.json()["host_id"] == host_id
    repeated = join(client, guest, lobby)
    assert repeated.status_code == 200
    assert repeated.json() == joined.json()
    assert get(client, guest, lobby).json() == joined.json()

    for _ in range(2):
        left = leave(client, guest, lobby)
        assert left.status_code == 204
        assert left.content == b""
    assert get(client, host, lobby).json() == lobby


def test_full_lobby_rejects_sixth_player_but_allows_rejoin_and_freed_slot(client):
    users = [login_user(client, f"player{i}") for i in range(6)]
    _, host = users[0]
    lobby = create_lobby(client, host)
    for _, headers in users[1:5]:
        assert join(client, headers, lobby).status_code == 200

    full = get(client, host, lobby).json()
    assert full["num_players"] == len(full["player_ids"]) == 5
    rejected = join(client, users[5][1], lobby)
    assert rejected.status_code == 409
    assert rejected.json()["detail"] == "Lobby is full"
    assert get(client, host, lobby).json() == full
    repeated = join(client, users[1][1], lobby)
    assert repeated.status_code == 200
    assert repeated.json() == full

    assert leave(client, users[1][1], lobby).status_code == 204
    joined = join(client, users[5][1], lobby)
    assert joined.status_code == 200
    assert joined.json()["num_players"] == 5
    assert str(users[1][0]) not in joined.json()["player_ids"]
    assert str(users[5][0]) in joined.json()["player_ids"]


def test_host_leaving_closes_the_lobby(client):
    # Current design (PR #8): the host leaving closes the room for everyone.
    _, host = login_user(client)
    _, guest = login_user(client, "guest")
    lobby = create_lobby(client, host)
    assert join(client, guest, lobby).status_code == 200

    assert leave(client, host, lobby).status_code == 204
    assert get(client, guest, lobby).status_code == 404
    assert join(client, guest, lobby).status_code == 404
    # The guest isn't stuck in the closed room and can host a new one.
    assert create_lobby(client, guest)["num_players"] == 1


def test_guest_leaving_keeps_the_lobby(client):
    host_id, host = login_user(client)
    _, guest = login_user(client, "guest")
    lobby = create_lobby(client, host)
    assert join(client, guest, lobby).status_code == 200
    assert leave(client, guest, lobby).status_code == 204
    remaining = get(client, host, lobby).json()
    assert remaining["host_id"] == host_id
    assert remaining["num_players"] == 1


def test_nonmember_leaving_does_not_change_lobby(client):
    _, host = login_user(client)
    _, stranger = login_user(client, "stranger")
    lobby = create_lobby(client, host)
    assert leave(client, stranger, lobby).status_code == 204
    assert get(client, host, lobby).json() == lobby


def test_leave_only_leaves_the_named_lobby(client):
    # Regression: /leave used to remove you from whatever room you were in,
    # even when the URL named a different room.
    _, host_a = login_user(client, "hosta")
    _, host_b = login_user(client, "hostb")
    guest_id, guest = login_user(client, "guest")
    room_a = create_lobby(client, host_a, "A")
    room_b = create_lobby(client, host_b, "B")
    assert join(client, guest, room_a).status_code == 200

    assert leave(client, guest, room_b).status_code == 204
    assert str(guest_id) in get(client, host_a, room_a).json()["player_ids"]
    assert get(client, host_b, room_b).json() == room_b


def test_host_leaving_deletes_only_that_lobby(client):
    _, first_host = login_user(client, "first")
    _, second_host = login_user(client, "second")
    first = create_lobby(client, first_host, "First")
    second = create_lobby(client, second_host, "Second")
    assert first["id"] != second["id"]

    assert leave(client, first_host, first).status_code == 204
    assert get(client, first_host, first).status_code == 404
    assert leave(client, first_host, first).status_code == 404
    assert join(client, first_host, first).status_code == 404
    assert get(client, second_host, second).json() == second


def test_creating_a_lobby_leaves_your_previous_one(client):
    # Current design (PR #8): one room per player; hosting a new room closes your old one.
    _, host = login_user(client)
    first = create_lobby(client, host, "First")
    second = create_lobby(client, host, "Second")
    assert get(client, host, first).status_code == 404
    assert get(client, host, second).json() == second


def test_host_rejoining_own_code_keeps_lobby(client):
    # Regression: join used to run leave_flow first, so a host re-entering their own
    # code deleted the room and got a 404.
    _, host = login_user(client)
    _, guest = login_user(client, "guest")
    lobby = create_lobby(client, host)
    assert join(client, guest, lobby).status_code == 200
    before = get(client, host, lobby).json()

    rejoined = join(client, host, lobby)
    assert rejoined.status_code == 200
    assert rejoined.json() == before
    assert get(client, guest, lobby).json() == before


def test_failed_join_does_not_leave_current_lobby(client):
    # Regression: a bad code or a full room used to kick you out of your room first.
    users = [login_user(client, f"player{i}") for i in range(5)]
    guest_id, guest = login_user(client, "guest")
    _, home_host = login_user(client, "homehost")
    home = create_lobby(client, home_host, "Home")
    assert join(client, guest, home).status_code == 200

    full = create_lobby(client, users[0][1], "Full")
    for _, headers in users[1:]:
        assert join(client, headers, full).status_code == 200

    missing = client.post("/lobbies/ZZZZZZ/join", headers=guest)
    assert missing.status_code == 404
    assert join(client, guest, full).status_code == 409
    assert str(guest_id) in get(client, guest, home).json()["player_ids"]
    assert get(client, guest, home).json()["num_players"] == 2


def test_joining_another_lobby_leaves_the_previous_one(client):
    _, host_a = login_user(client, "hosta")
    _, host_b = login_user(client, "hostb")
    guest_id, guest = login_user(client, "guest")
    room_a = create_lobby(client, host_a, "A")
    room_b = create_lobby(client, host_b, "B")
    assert join(client, guest, room_a).status_code == 200

    moved = join(client, guest, room_b)
    assert moved.status_code == 200
    assert str(guest_id) in moved.json()["player_ids"]
    assert get(client, host_a, room_a).json() == room_a


@pytest.mark.parametrize("method,suffix", [("GET", ""), ("POST", "/leave")])
@pytest.mark.parametrize("lobby_id,expected", [(str(uuid4()), 404), ("invalid-id", 422)])
def test_missing_and_invalid_lobby_ids(client, method, suffix, lobby_id, expected):
    # Regression: unknown ids raised KeyError and malformed ids ValueError (both 500).
    _, headers = login_user(client)
    response = client.request(method, f"/lobbies/{lobby_id}{suffix}", headers=headers)
    assert response.status_code == expected


@pytest.mark.parametrize("code", ["ZZZZZZ", "invalid-code"])
def test_unknown_lobby_code(client, code):
    _, host = login_user(client)
    create_lobby(client, host)
    _, headers = login_user(client, "guest")
    assert client.post(f"/lobbies/{code}/join", headers=headers).status_code == 404


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer invalid-token"}])
@pytest.mark.parametrize("method,suffix", [
    ("POST", "/createLobby"), ("GET", "/{id}"),
    ("POST", "/{code}/join"), ("POST", "/{id}/leave"),
])
def test_lobby_endpoints_require_login(client, method, suffix, headers):
    _, host = login_user(client)
    lobby = create_lobby(client, host)
    path = "/lobbies" + suffix.format(id=lobby["id"], code=lobby["code"])
    response = client.request(method, path, headers=headers, json={"name": "Not allowed"})
    assert response.status_code == 401
    assert get(client, host, lobby).json() == lobby
    assert len(lobby_router.lobby_manager.get_all_lobbies()) == 1
