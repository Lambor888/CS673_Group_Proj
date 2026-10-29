import pytest
from starlette.websockets import WebSocketDisconnect

from app.modules.auth.models import User, FriendRequest
from app.modules.auth.security import create_access_token


@pytest.fixture
def accounts(db_session):
    users = [User(username=name, password_hash="unused") for name in ("alice", "bob", "carol")]
    db_session.add_all(users)
    db_session.commit()
    return [{"id": user.id, "token": create_access_token(user.id),
             "headers": {"Authorization": f"Bearer {create_access_token(user.id)}"}}
            for user in users]


def send(client, sender, recipient):
    return client.post("/auth/friend-requests", headers=sender["headers"],
                       json={"recipient_id": recipient["id"]})


def pending(client, account, direction="incoming"):
    return client.get(f"/auth/friend-requests/pending?direction={direction}",
                      headers=account["headers"]).json()


def friend_ids(client, account):
    return [u["id"] for u in client.get("/auth/friends", headers=account["headers"]).json()]


def test_pending_accept_and_mutual_removal(client, accounts, db_session):
    alice, bob, _ = accounts
    response = send(client, alice, bob)
    assert response.status_code == 201
    request = response.json()
    assert request["status"] == "pending"
    assert db_session.get(FriendRequest, request["id"]).status == "pending"
    assert pending(client, bob) == [request]
    assert pending(client, alice) == []
    assert pending(client, alice, "outgoing") == [request]
    assert friend_ids(client, alice) == friend_ids(client, bob) == []
    path = f"/auth/friend-requests/{request['id']}/accept"
    assert client.post(path, headers=bob["headers"]).json()["status"] == "accepted"
    assert client.post(path, headers=bob["headers"]).status_code == 200
    assert friend_ids(client, alice) == [bob["id"]]
    assert friend_ids(client, bob) == [alice["id"]]
    assert pending(client, bob) == []
    assert send(client, alice, bob).status_code == 409
    for _ in range(2):
        assert client.delete(f"/auth/friends/{bob['id']}", headers=alice["headers"]).status_code == 204
    assert friend_ids(client, alice) == friend_ids(client, bob) == []
    new_request = send(client, bob, alice)
    assert new_request.status_code == 201
    assert new_request.json()["id"] != request["id"]
    assert client.post(path, headers=bob["headers"]).status_code == 404


def test_only_recipient_can_respond_and_rejection_can_be_retried(client, accounts):
    alice, bob, carol = accounts
    request = send(client, alice, bob).json()
    for actor in (alice, carol):
        for action in ("accept", "reject"):
            assert client.post(f"/auth/friend-requests/{request['id']}/{action}",
                               headers=actor["headers"]).status_code == 404
    assert pending(client, carol) == []
    assert send(client, alice, bob).status_code == 409
    assert send(client, bob, alice).status_code == 409
    path = f"/auth/friend-requests/{request['id']}"
    assert client.post(path + "/reject", headers=bob["headers"]).json()["status"] == "rejected"
    assert client.post(path + "/accept", headers=bob["headers"]).status_code == 409
    assert friend_ids(client, alice) == friend_ids(client, bob) == []
    assert send(client, alice, bob).status_code == 201


def test_invalid_requests_and_authentication(client, accounts):
    alice, _, _ = accounts
    assert send(client, alice, alice).status_code == 400
    assert send(client, alice, {"id": 999999}).status_code == 404
    assert client.post("/auth/friend-requests", headers=alice["headers"],
                       json={"recipient_id": -1}).status_code == 422
    for method, path, body in [
        ("get", "/auth/friends", None),
        ("get", "/auth/friend-requests/pending", None),
        ("post", "/auth/friend-requests", {"recipient_id": alice["id"]}),
        ("post", "/auth/friend-requests/00000000-0000-0000-0000-000000000000/accept", None),
        ("post", "/auth/friend-requests/00000000-0000-0000-0000-000000000000/reject", None),
        ("delete", f"/auth/friends/{alice['id']}", None),
    ]:
        assert client.request(method, path, json=body).status_code == 401


def test_live_notifications_and_offline_pending_replay(client, accounts):
    alice, bob, _ = accounts
    with client.websocket_connect(f"/auth/notifications/ws?token={bob['token']}") as socket:
        assert socket.receive_json() == {"type": "friend_requests_pending", "data": []}
        request = send(client, alice, bob).json()
        assert socket.receive_json() == {"type": "friend_request", "data": request}
    # Reconnecting replays the persisted request, even after missing live events.
    with client.websocket_connect(f"/auth/notifications/ws?token={bob['token']}") as bob_ws:
        assert bob_ws.receive_json()["data"] == [request]
        with client.websocket_connect(f"/auth/notifications/ws?token={alice['token']}") as alice_ws:
            alice_ws.receive_json()
            result = client.post(f"/auth/friend-requests/{request['id']}/accept",
                                 headers=bob["headers"]).json()
            event = {"type": "friend_request_updated", "data": result}
            assert alice_ws.receive_json() == event
            assert bob_ws.receive_json() == event
            client.delete(f"/auth/friends/{bob['id']}", headers=alice["headers"])
            assert alice_ws.receive_json()["data"] == {"friend_id": bob["id"]}
            assert bob_ws.receive_json()["data"] == {"friend_id": alice["id"]}


def test_notification_socket_rejects_invalid_token(client):
    with pytest.raises(WebSocketDisconnect) as error:
        with client.websocket_connect("/auth/notifications/ws?token=invalid"):
            pass
    assert error.value.code == 4401
