import pytest
from starlette.websockets import WebSocketDisconnect

from app.modules.auth.models import User, RevokedToken
from app.modules.auth.security import create_access_token, token_digest


def test_logout_revokes_current_token_only(client, db_session):
    user = User(username="alice", password_hash="unused")
    db_session.add(user)
    db_session.commit()
    first, second = create_access_token(user.id), create_access_token(user.id)
    assert first != second
    headers = {"Authorization": f"Bearer {first}"}
    assert client.get("/auth/me", headers=headers).status_code == 200
    response = client.post("/auth/logout", headers=headers)
    assert response.status_code == 204
    assert response.content == b""
    db_session.expire_all()
    assert db_session.get(RevokedToken, token_digest(first)) is not None
    assert client.get("/auth/me", headers=headers).status_code == 401
    assert client.get("/auth/friends", headers=headers).status_code == 401
    assert client.post("/auth/logout", headers=headers).status_code == 401
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {second}"}).status_code == 200
    with pytest.raises(WebSocketDisconnect) as error:
        with client.websocket_connect(f"/auth/notifications/ws?token={first}"):
            pass
    assert error.value.code == 4401


def test_logout_requires_authentication(client):
    assert client.post("/auth/logout").status_code == 401
    assert client.post("/auth/logout", headers={"Authorization": "Bearer invalid"}).status_code == 401
