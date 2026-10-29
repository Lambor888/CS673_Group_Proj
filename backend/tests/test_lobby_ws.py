"""Lobby websocket presence: a dropped socket is not a leave.

Refreshing, going from the lobby page to the game page, or a network blip all close the
socket. The player keeps their seat for a grace period and is only removed if they don't
reconnect in time. These tests run inside `with client:` so every request and socket shares
one event loop, and the grace-period timers survive between calls like they do in uvicorn.
"""

import time
import uuid

import pytest
from starlette.websockets import WebSocketDisconnect

from app.modules.lobby import router as lobby_router
from app.modules.lobby.service import ConnectionManager, LobbyManager

from tests.test_lobby_api import create_lobby, join, leave, login_user


@pytest.fixture(autouse=True)
def fresh_state(monkeypatch):
    monkeypatch.setattr(lobby_router, "lobby_manager", LobbyManager())
    monkeypatch.setattr(lobby_router, "connection_manager", ConnectionManager())
    # Long enough that nothing expires mid-test unless a test shortens it.
    monkeypatch.setattr(lobby_router, "DISCONNECT_GRACE_SECONDS", 30.0)


@pytest.fixture
def live(client):
    with client:
        yield client


def token_of(headers):
    return headers["Authorization"].removeprefix("Bearer ")


def connect(client, headers, lobby_id):
    return client.websocket_connect(f"/ws/{lobby_id}?token={token_of(headers)}")


def receive_until(ws, msg_type):
    while True:
        msg = ws.receive_json()
        if msg["type"] == msg_type:
            return msg


def members(lobby):
    room = lobby_router.lobby_manager.lobbies.get(uuid.UUID(lobby["id"]))
    return set(room.players) if room else None


def wait_for(condition, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.02)
    return condition()


def host_and_guest(client):
    host_id, host = login_user(client)
    guest_id, guest = login_user(client, "guest")
    lobby = create_lobby(client, host)
    assert join(client, guest, lobby).status_code == 200
    return lobby, (host_id, host), (guest_id, guest)


def pending():
    return lobby_router.connection_manager.pending_leaves


def test_connect_sends_the_lobby(live):
    lobby, (host_id, host), (guest_id, _) = host_and_guest(live)
    with connect(live, host, lobby["id"]) as ws:
        msg = ws.receive_json()
    assert msg["type"] == "lobby_update"
    assert msg["data"]["id"] == lobby["id"]
    assert set(msg["data"]["player_ids"]) == {str(host_id), str(guest_id)}


@pytest.mark.parametrize("who", ["bad-token", "outsider", "bad-id", "unknown-id"])
def test_rejected_sockets_get_close_code_4401(live, who):
    lobby, (_, host), _ = host_and_guest(live)
    _, outsider = login_user(live, "outsider")
    url = {
        "bad-token": f"/ws/{lobby['id']}?token=nope",
        "outsider": f"/ws/{lobby['id']}?token={token_of(outsider)}",
        "bad-id": f"/ws/not-a-uuid?token={token_of(host)}",
        "unknown-id": f"/ws/00000000-0000-0000-0000-000000000000?token={token_of(host)}",
    }[who]
    # Accepted then closed, so a browser sees 4401 rather than a generic 1006 failure.
    with live.websocket_connect(url) as ws:
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
    assert closed.value.code == 4401


def test_dropped_socket_keeps_the_seat_during_the_grace_period(live):
    lobby, (host_id, _), (guest_id, guest) = host_and_guest(live)
    with connect(live, guest, lobby["id"]) as ws:
        ws.receive_json()
    assert wait_for(lambda: guest_id in pending())
    assert members(lobby) == {host_id, guest_id}


def test_player_is_removed_once_the_grace_period_runs_out(live, monkeypatch):
    monkeypatch.setattr(lobby_router, "DISCONNECT_GRACE_SECONDS", 0.1)
    lobby, (host_id, host), (guest_id, guest) = host_and_guest(live)
    with connect(live, host, lobby["id"]) as host_ws:
        host_ws.receive_json()
        with connect(live, guest, lobby["id"]) as guest_ws:
            guest_ws.receive_json()

        update = receive_until(host_ws, "lobby_update")
        assert set(update["data"]["player_ids"]) == {str(host_id)}
        assert receive_until(host_ws, "chat")["text"] == "guest left the lobby."
    assert members(lobby) == {host_id}
    assert guest_id not in pending()
    # And once they're out, their old socket url is refused.
    with connect(live, guest, lobby["id"]) as ws:
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
    assert closed.value.code == 4401


def test_host_drop_closes_the_lobby_after_the_grace_period(live, monkeypatch):
    monkeypatch.setattr(lobby_router, "DISCONNECT_GRACE_SECONDS", 0.1)
    lobby, (_, host), (_, guest) = host_and_guest(live)
    with connect(live, guest, lobby["id"]) as guest_ws:
        guest_ws.receive_json()
        with connect(live, host, lobby["id"]) as host_ws:
            host_ws.receive_json()
        assert receive_until(guest_ws, "lobby_closed") == {"type": "lobby_closed"}
    assert members(lobby) is None


def test_reconnecting_cancels_the_pending_leave(live, monkeypatch):
    monkeypatch.setattr(lobby_router, "DISCONNECT_GRACE_SECONDS", 0.3)
    lobby, (host_id, _), (guest_id, guest) = host_and_guest(live)
    with connect(live, guest, lobby["id"]) as ws:  # e.g. a page refresh
        ws.receive_json()
    assert wait_for(lambda: guest_id in pending())
    with connect(live, guest, lobby["id"]) as ws:
        assert ws.receive_json()["type"] == "lobby_update"
        assert guest_id not in pending()
        time.sleep(0.5)  # well past the original deadline
        assert members(lobby) == {host_id, guest_id}


def test_starting_the_game_does_not_empty_the_lobby(live, monkeypatch):
    # The bug: game_started sends everyone from /lobby/:id to /game/:id. The lobby page
    # unmounts and closes its socket, which used to count as leaving, so the host's room
    # was deleted and every guest was kicked the moment the game started.
    monkeypatch.setattr(lobby_router, "DISCONNECT_GRACE_SECONDS", 0.3)
    lobby, (host_id, host), (guest_id, guest) = host_and_guest(live)

    with connect(live, host, lobby["id"]) as host_ws, connect(live, guest, lobby["id"]) as guest_ws:
        host_ws.receive_json()
        guest_ws.receive_json()
        started = live.post(f"/lobbies/{lobby['id']}/start", headers=host)
        assert started.status_code == 200
        assert receive_until(host_ws, "game_started")
        assert receive_until(guest_ws, "game_started")
    # Lobby page sockets are closed; the game page opens new ones.
    with connect(live, host, lobby["id"]) as host_ws, connect(live, guest, lobby["id"]) as guest_ws:
        host_ws.receive_json()
        guest_ws.receive_json()
        time.sleep(0.5)
        assert members(lobby) == {host_id, guest_id}
        assert pending() == {}


def test_explicit_leave_is_immediate_and_cancels_the_timer(live):
    lobby, (host_id, _), (guest_id, guest) = host_and_guest(live)
    with connect(live, guest, lobby["id"]) as ws:
        ws.receive_json()
        assert leave(live, guest, lobby).status_code == 204
        with pytest.raises(WebSocketDisconnect) as closed:
            while True:
                ws.receive_json()
        assert closed.value.code == 1000
    assert members(lobby) == {host_id}
    assert guest_id not in pending()


def test_pending_leave_only_applies_to_the_room_that_was_dropped(live, monkeypatch):
    monkeypatch.setattr(lobby_router, "DISCONNECT_GRACE_SECONDS", 0.2)
    lobby, (host_id, _), (guest_id, guest) = host_and_guest(live)
    _, other_host = login_user(live, "bob")
    other = create_lobby(live, other_host)

    with connect(live, guest, lobby["id"]) as ws:
        ws.receive_json()
    assert wait_for(lambda: guest_id in pending())
    # Joining another room leaves the old one right away; the timer must not follow them.
    assert join(live, guest, other).status_code == 200
    assert members(lobby) == {host_id}
    time.sleep(0.4)
    assert guest_id in members(other)


def test_second_tab_replaces_the_first_with_4409(live):
    lobby, (host_id, _), (guest_id, guest) = host_and_guest(live)
    with connect(live, guest, lobby["id"]) as first:
        first.receive_json()
        with connect(live, guest, lobby["id"]) as second:
            second.receive_json()
            with pytest.raises(WebSocketDisconnect) as closed:
                first.receive_json()
            assert closed.value.code == 4409
            # The replaced socket closing is not a disconnect of the player.
            assert guest_id not in pending()
    assert members(lobby) == {host_id, guest_id}
