from datetime import datetime, timedelta, timezone

import jwt

from app.config import settings


def register(client, username="alice", password="password123"):
    client.post("/auth/register", json={"username": username, "password": password})


def login(client, username="alice", password="password123"):
    # Login takes form fields, not JSON.
    return client.post("/auth/login", data={"username": username, "password": password})


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def test_login_returns_token(client):
    register(client)
    r = login(client)
    assert r.status_code == 200
    assert r.json()["token_type"] == "bearer"
    assert r.json()["access_token"]


def test_login_username_is_case_insensitive(client):
    register(client, username="alice")
    assert login(client, username="ALICE").status_code == 200


def test_wrong_password_and_unknown_user_look_the_same(client):
    register(client)
    wrong_password = login(client, password="wrong-password")
    unknown_user = login(client, username="nobody")
    assert wrong_password.status_code == unknown_user.status_code == 401
    assert wrong_password.json() == unknown_user.json()


def test_me_with_token(client):
    register(client)
    token = login(client).json()["access_token"]
    r = client.get("/auth/me", headers=auth_header(token))
    assert r.status_code == 200
    assert r.json()["username"] == "alice"


def test_me_without_token(client):
    assert client.get("/auth/me").status_code == 401


def test_me_with_bad_token(client):
    assert client.get("/auth/me", headers=auth_header("not-a-token")).status_code == 401


def test_me_with_expired_token(client):
    register(client)
    expired = jwt.encode(
        {"sub": "1", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    assert client.get("/auth/me", headers=auth_header(expired)).status_code == 401


def test_me_with_forged_token(client):
    register(client)
    forged = jwt.encode(
        {"sub": "1", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        "someone-elses-secret-at-least-32-bytes",
        algorithm="HS256",
    )
    assert client.get("/auth/me", headers=auth_header(forged)).status_code == 401


def test_me_with_token_that_never_expires(client):
    register(client)
    no_expiry = jwt.encode({"sub": "1"}, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    assert client.get("/auth/me", headers=auth_header(no_expiry)).status_code == 401
