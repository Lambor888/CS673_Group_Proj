"""Accounts: email at sign-up, login by email, Google sign-in, profile changes and stats.

Google ID tokens are signed here with a throwaway RSA key standing in for Google's, so the real
checks (signature, audience, issuer, expiry, verified email) run exactly as in production.
"""

import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.config import settings
from app.modules.auth import google
from app.modules.auth.models import User
from app.modules.singlePlayer import router as single_player
from app.modules.location import service as location_service

CLIENT_ID = "test-client.apps.googleusercontent.com"
GOOGLE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(autouse=True)
def google_configured(monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", CLIENT_ID)
    monkeypatch.setattr(google, "_signing_key", lambda token: GOOGLE_KEY.public_key())


def google_token(sub="google-123", email="Jane.Doe@gmail.com", key=GOOGLE_KEY, **overrides):
    now = int(time.time())
    claims = {
        "iss": "https://accounts.google.com",
        "aud": CLIENT_ID,
        "sub": sub,
        "email": email,
        "email_verified": True,
        "name": "Jane Doe",
        "iat": now,
        "exp": now + 3600,
        **overrides,
    }
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, key, algorithm="RS256")


def google_login(client, token):
    return client.post("/auth/google", json={"credential": token})


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def register(client, username="alice", email=None, password="password123"):
    return client.post(
        "/auth/register",
        json={"username": username, "email": email or f"{username}@example.com", "password": password},
    )


def login(client, identifier="alice", password="password123"):
    return client.post("/auth/login", data={"username": identifier, "password": password})


def password_user(client, username="alice", email=None):
    assert register(client, username, email).status_code == 201
    return bearer(login(client, username).json()["access_token"])


# --- Sign-up and login ---


def test_register_returns_the_account(client):
    r = register(client, "alice", "Alice@Example.COM")
    assert r.status_code == 201
    body = r.json()
    assert body["username"] == "alice"
    assert body["email"] == "alice@example.com"
    assert body["has_password"] is True
    assert body["google_connected"] is False
    assert "password_hash" not in body and "google_sub" not in body


@pytest.mark.parametrize("email", [None, "", "not-an-email", "a@b", "x" * 250 + "@example.com"])
def test_register_needs_a_valid_email(client, email):
    body = {"username": "alice", "password": "password123"}
    if email is not None:
        body["email"] = email
    assert client.post("/auth/register", json=body).status_code == 422


def test_email_is_unique_ignoring_case(client):
    assert register(client, "alice", "alice@example.com").status_code == 201
    r = register(client, "bob", "ALICE@example.com")
    assert r.status_code == 409
    assert r.json()["detail"] == "An account with this email already exists"


def test_login_with_email(client):
    register(client, "alice", "alice@example.com")
    r = login(client, "  Alice@Example.com ")
    assert r.status_code == 200
    me = client.get("/auth/me", headers=bearer(r.json()["access_token"])).json()
    assert me["username"] == "alice"


def test_wrong_password_by_email_looks_like_any_other_failure(client):
    register(client, "alice", "alice@example.com")
    for identifier in ("alice@example.com", "nobody@example.com"):
        r = login(client, identifier, "wrong-password")
        assert r.status_code == 401
        assert r.json()["detail"] == "Invalid username or password"


# --- Google sign-in ---


def test_google_sign_in_creates_an_account(client, db_session):
    r = google_login(client, google_token())
    assert r.status_code == 200
    assert r.json()["new_account"] is True
    me = client.get("/auth/me", headers=bearer(r.json()["access_token"])).json()
    assert me["username"] == "jane_doe"
    assert me["email"] == "jane.doe@gmail.com"
    assert me["has_password"] is False
    assert me["google_connected"] is True
    assert db_session.query(User).filter_by(username="jane_doe").one().google_sub == "google-123"


def test_google_sign_in_again_logs_into_the_same_account(client):
    first = google_login(client, google_token())
    # Same Google account even if its email changed since.
    again = google_login(client, google_token(email="jane@newmail.com"))
    assert again.status_code == 200
    assert again.json()["new_account"] is False
    first_me = client.get("/auth/me", headers=bearer(first.json()["access_token"])).json()
    again_me = client.get("/auth/me", headers=bearer(again.json()["access_token"])).json()
    assert again_me["id"] == first_me["id"]


@pytest.mark.parametrize(
    ("email", "expected"),
    [
        ("Jane.Doe+games@gmail.com", "jane_doe_games"),
        ("a@gmail.com", "player_a"),
        ("...@gmail.com", "player"),
        ("averyveryverylongname@gmail.com", "averyveryverylo"),
    ],
)
def test_google_usernames_are_valid(client, email, expected):
    r = google_login(client, google_token(sub=email, email=email))
    me = client.get("/auth/me", headers=bearer(r.json()["access_token"])).json()
    assert me["username"] == expected
    assert 3 <= len(me["username"]) <= 20


def test_google_username_avoids_taken_names(client):
    register(client, "jane_doe", "someone@example.com")
    r = google_login(client, google_token())
    me = client.get("/auth/me", headers=bearer(r.json()["access_token"])).json()
    assert me["username"].startswith("jane_doe_") and len(me["username"]) <= 20
    # And the result is a username the rest of the app accepts.
    assert client.patch("/auth/me", headers=bearer(r.json()["access_token"]), json={"username": me["username"]}).status_code == 200


def test_google_does_not_take_over_an_account_with_the_same_email(client):
    # Emails aren't verified at sign-up, so matching on email alone would let whoever
    # registered "jane.doe@gmail.com" first share Jane's account.
    register(client, "squatter", "jane.doe@gmail.com")
    r = google_login(client, google_token())
    assert r.status_code == 409
    assert "connect Google from your profile" in r.json()["detail"]


@pytest.mark.parametrize(
    "bad",
    [
        {"aud": "someone-elses-app"},
        {"iss": "https://evil.example.com"},
        {"exp": int(time.time()) - 3600},
        {"sub": None},
        {"key": OTHER_KEY},
        {"email_verified": False},
        {"email": None},
    ],
)
def test_bad_google_tokens_are_rejected(client, db_session, bad):
    r = google_login(client, google_token(**bad))
    assert r.status_code == 401
    assert db_session.query(User).count() == 0


def test_garbage_credential_is_rejected(client):
    assert google_login(client, "not-a-jwt").status_code == 401
    assert google_login(client, "").status_code == 422


def test_google_sign_in_off_without_a_client_id(client, monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", "")
    r = google_login(client, google_token())
    assert r.status_code == 503
    assert r.json()["detail"] == "Google sign-in isn't set up on this server."


def test_google_unreachable_is_a_503(client, monkeypatch):
    def unreachable(token):
        raise jwt.PyJWKClientConnectionError("no network")

    monkeypatch.setattr(google, "_signing_key", unreachable)
    assert google_login(client, google_token()).status_code == 503


def test_google_only_accounts_cannot_password_login(client):
    google_login(client, google_token())
    for password in ("password123", "dummy-password", ""):
        assert login(client, "jane_doe", password).status_code in (401, 422)
        assert login(client, "jane.doe@gmail.com", password).status_code in (401, 422)


# --- Connecting Google to an existing account ---


def test_connect_google_then_sign_in_with_either(client):
    headers = password_user(client, "alice", "alice@example.com")
    r = client.post("/auth/google/link", headers=headers, json={"credential": google_token(sub="g-alice")})
    assert r.status_code == 200
    assert r.json()["google_connected"] is True
    assert r.json()["email"] == "alice@example.com"  # their own email is kept

    via_google = google_login(client, google_token(sub="g-alice"))
    assert via_google.status_code == 200 and via_google.json()["new_account"] is False
    me = client.get("/auth/me", headers=bearer(via_google.json()["access_token"])).json()
    assert me["username"] == "alice"
    assert login(client, "alice").status_code == 200
    # Connecting the same Google account again is fine.
    assert client.post("/auth/google/link", headers=headers, json={"credential": google_token(sub="g-alice")}).status_code == 200


def test_connect_google_fills_in_a_missing_email(client, db_session):
    headers = password_user(client, "alice")
    db_session.query(User).filter_by(username="alice").update({"email": None})  # an account from before emails
    db_session.commit()
    r = client.post("/auth/google/link", headers=headers, json={"credential": google_token(sub="g-alice")})
    assert r.json()["email"] == "jane.doe@gmail.com"


def test_connect_google_conflicts(client):
    taken = google_login(client, google_token(sub="g-jane"))
    assert taken.status_code == 200
    headers = password_user(client, "alice")

    r = client.post("/auth/google/link", headers=headers, json={"credential": google_token(sub="g-jane")})
    assert r.status_code == 409
    assert r.json()["detail"] == "That Google account is already used by another player."

    assert client.post("/auth/google/link", headers=headers, json={"credential": google_token(sub="g-alice", email="a@gmail.com")}).status_code == 200
    r = client.post("/auth/google/link", headers=headers, json={"credential": google_token(sub="g-other", email="o@gmail.com")})
    assert r.status_code == 409
    assert r.json()["detail"] == "Your account is already connected to a different Google account."


def test_connect_google_needs_login(client):
    assert client.post("/auth/google/link", json={"credential": google_token()}).status_code == 401


# --- Profile changes ---


def test_change_username(client):
    headers = password_user(client, "alice")
    password_user(client, "bob")
    r = client.patch("/auth/me", headers=headers, json={"username": "Alice_2"})
    assert r.status_code == 200 and r.json()["username"] == "alice_2"
    assert login(client, "alice_2").status_code == 200
    assert login(client, "alice").status_code == 401

    taken = client.patch("/auth/me", headers=headers, json={"username": "BOB"})
    assert taken.status_code == 409
    assert client.patch("/auth/me", headers=headers, json={"username": "no spaces"}).status_code == 422
    # Keeping your own name (any case) is not a conflict.
    assert client.patch("/auth/me", headers=headers, json={"username": "ALICE_2"}).status_code == 200


def test_change_password(client):
    headers = password_user(client, "alice")
    wrong = client.post("/auth/password", headers=headers, json={"current_password": "nope", "new_password": "new-password-1"})
    assert wrong.status_code == 400
    assert wrong.json()["detail"] == "Current password is incorrect"
    missing = client.post("/auth/password", headers=headers, json={"new_password": "new-password-1"})
    assert missing.status_code == 400
    short = client.post("/auth/password", headers=headers, json={"current_password": "password123", "new_password": "short"})
    assert short.status_code == 422

    ok = client.post("/auth/password", headers=headers, json={"current_password": "password123", "new_password": "new-password-1"})
    assert ok.status_code == 204
    assert login(client, "alice", "password123").status_code == 401
    assert login(client, "alice", "new-password-1").status_code == 200


def test_google_only_account_can_set_a_first_password(client):
    headers = bearer(google_login(client, google_token()).json()["access_token"])
    r = client.post("/auth/password", headers=headers, json={"new_password": "my-first-password"})
    assert r.status_code == 204
    assert client.get("/auth/me", headers=headers).json()["has_password"] is True
    assert login(client, "jane.doe@gmail.com", "my-first-password").status_code == 200
    # From now on changing it needs the current one.
    again = client.post("/auth/password", headers=headers, json={"new_password": "another-password"})
    assert again.status_code == 400


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [("get", "/auth/me", None), ("patch", "/auth/me", {"username": "x_y_z"}),
     ("post", "/auth/password", {"new_password": "whatever-123"}), ("get", "/profile/stats", None)],
)
def test_account_endpoints_need_login(client, method, path, body):
    kwargs = {"json": body} if body is not None else {}
    assert getattr(client, method)(path, **kwargs).status_code == 401


# --- Stats ---


def test_stats_start_empty(client):
    headers = password_user(client, "alice")
    assert client.get("/profile/stats", headers=headers).json() == {
        "rounds_played": 0,
        "total_score": 0,
        "best_score": None,
        "average_score": None,
        "best_distance_km": None,
        "average_distance_km": None,
    }


def test_single_player_rounds_count_once_in_stats(client, monkeypatch):
    single_player.rounds.clear()
    headers = password_user(client, "alice")
    other = password_user(client, "bob")
    locations = iter([
        location_service.Location(pano_id="a", lat=0, lng=0),
        location_service.Location(pano_id="b", lat=10, lng=10),
    ])
    monkeypatch.setattr(single_player, "generate_location", lambda exclude=None: next(locations))

    first = client.post("/singleplayer/round", headers=headers, json={}).json()
    guess = f"/singleplayer/round/{first['round_id']}/guess"
    perfect = client.post(guess, headers=headers, json={"lat": 0, "lng": 0}).json()
    client.post(guess, headers=headers, json={"lat": 0, "lng": 0})  # a retried request
    second = client.post("/singleplayer/round", headers=headers, json={"previous_round_id": first["round_id"]}).json()
    far = client.post(f"/singleplayer/round/{second['round_id']}/guess", headers=headers, json={"lat": 50, "lng": 50}).json()
    single_player.rounds.clear()

    stats = client.get("/profile/stats", headers=headers).json()
    assert stats["rounds_played"] == 2
    assert stats["total_score"] == perfect["score"] + far["score"]
    assert stats["best_score"] == 5000
    assert stats["best_distance_km"] == 0
    assert stats["average_distance_km"] == pytest.approx(far["distance_km"] / 2, abs=0.01)
    # Only your own rounds.
    assert client.get("/profile/stats", headers=other).json()["rounds_played"] == 0
