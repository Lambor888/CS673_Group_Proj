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


def test_create_and_get_lobby(client):
    host_id, headers = login_user(client)
    lobby = create_lobby(client, headers, "  Friends  ")
    assert lobby == {
        "id": lobby["id"],
        "name": "Friends",
        "player_ids": {str(host_id): {"id": host_id}},
        "host_id": host_id,
        "num_players": 1,
        "max_players": 5,
        "flag": False,
    }
    response = client.get(f"/lobbies/{lobby['id']}", headers=headers)
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
    path = f"/lobbies/{lobby['id']}"

    joined = client.post(f"{path}/join", headers=guest)
    assert joined.status_code == 200
    assert joined.json()["num_players"] == 2
    assert joined.json()["player_ids"] == {
        str(host_id): {"id": host_id}, str(guest_id): {"id": guest_id},
    }
    assert joined.json()["host_id"] == host_id
    repeated = client.post(f"{path}/join", headers=guest)
    assert repeated.status_code == 200
    assert repeated.json() == joined.json()
    assert client.get(path, headers=guest).json() == joined.json()

    for _ in range(2):
        left = client.post(f"{path}/leave", headers=guest)
        assert left.status_code == 204
        assert left.content == b""
    assert client.get(path, headers=host).json() == lobby


def test_full_lobby_rejects_sixth_player_but_allows_rejoin_and_freed_slot(client):
    users = [login_user(client, f"player{i}") for i in range(6)]
    _, host = users[0]
    path = f"/lobbies/{create_lobby(client, host)['id']}"
    for _, headers in users[1:5]:
        assert client.post(f"{path}/join", headers=headers).status_code == 200

    full = client.get(path, headers=host).json()
    assert full["num_players"] == len(full["player_ids"]) == 5
    rejected = client.post(f"{path}/join", headers=users[5][1])
    assert rejected.status_code == 409
    assert rejected.json()["detail"] == "Lobby is full"
    assert client.get(path, headers=host).json() == full
    repeated = client.post(f"{path}/join", headers=users[1][1])
    assert repeated.status_code == 200
    assert repeated.json() == full

    assert client.post(f"{path}/leave", headers=users[1][1]).status_code == 204
    joined = client.post(f"{path}/join", headers=users[5][1])
    assert joined.status_code == 200
    assert joined.json()["num_players"] == 5
    assert str(users[1][0]) not in joined.json()["player_ids"]
    assert str(users[5][0]) in joined.json()["player_ids"]


def test_host_leaving_passes_host_to_first_remaining_player(client):
    _, host = login_user(client)
    guest_id, guest = login_user(client, "guest")
    last_id, last = login_user(client, "lastguest")
    path = f"/lobbies/{create_lobby(client, host)['id']}"
    assert client.post(f"{path}/join", headers=guest).status_code == 200
    assert client.post(f"{path}/join", headers=last).status_code == 200

    assert client.post(f"{path}/leave", headers=host).status_code == 204
    remaining = client.get(path, headers=guest).json()
    assert remaining["host_id"] == guest_id
    assert remaining["num_players"] == 2
    assert client.post(f"{path}/leave", headers=guest).status_code == 204
    remaining = client.get(path, headers=last).json()
    assert remaining["host_id"] == last_id
    assert remaining["num_players"] == 1


def test_nonmember_leaving_does_not_change_lobby(client):
    _, host = login_user(client)
    _, stranger = login_user(client, "stranger")
    lobby = create_lobby(client, host)
    path = f"/lobbies/{lobby['id']}"
    assert client.post(f"{path}/leave", headers=stranger).status_code == 204
    assert client.get(path, headers=host).json() == lobby


def test_last_player_leaving_deletes_only_that_lobby(client):
    _, host = login_user(client)
    first = create_lobby(client, host, "First")
    second = create_lobby(client, host, "Second")
    assert first["id"] != second["id"]
    path = f"/lobbies/{first['id']}"
    assert client.post(f"{path}/leave", headers=host).status_code == 204
    for method, suffix in [("GET", ""), ("POST", "/join"), ("POST", "/leave")]:
        assert client.request(method, path + suffix, headers=host).status_code == 404
    assert client.get(f"/lobbies/{second['id']}", headers=host).json() == second


@pytest.mark.parametrize("method,suffix", [("GET", ""), ("POST", "/join"), ("POST", "/leave")])
@pytest.mark.parametrize("lobby_id,expected", [(str(uuid4()), 404), ("invalid-id", 422)])
def test_missing_and_invalid_lobby_ids(client, method, suffix, lobby_id, expected):
    _, headers = login_user(client)
    response = client.request(method, f"/lobbies/{lobby_id}{suffix}", headers=headers)
    assert response.status_code == expected


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer invalid-token"}])
@pytest.mark.parametrize("method,suffix", [
    ("POST", "/createLobby"), ("GET", "/{id}"),
    ("POST", "/{id}/join"), ("POST", "/{id}/leave"),
])
def test_lobby_endpoints_require_login(client, method, suffix, headers):
    _, host = login_user(client)
    lobby = create_lobby(client, host)
    path = "/lobbies" + suffix.format(id=lobby["id"])
    response = client.request(method, path, headers=headers, json={"name": "Not allowed"})
    assert response.status_code == 401
    assert client.get(f"/lobbies/{lobby['id']}", headers=host).json() == lobby
    assert len(lobby_router.lobby_manager.get_all_lobbies()) == 1
