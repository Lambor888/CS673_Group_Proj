from app.modules.auth.models import User


def register(client, username="alice", password="password123"):
    return client.post("/auth/register", json={"username": username, "password": password})


def test_register_creates_user(client):
    r = register(client)
    assert r.status_code == 201
    assert r.json()["username"] == "alice"
    assert "id" in r.json()


def test_register_never_returns_password(client):
    body = register(client).json()
    assert "password" not in body
    assert "password_hash" not in body


def test_password_is_stored_hashed(client, db_session):
    register(client, password="password123")
    user = db_session.query(User).filter_by(username="alice").one()
    assert user.password_hash != "password123"
    assert user.password_hash.startswith("$argon2id$")


def test_duplicate_username_is_rejected(client):
    register(client, username="alice")
    r = register(client, username="ALICE")  # same name, different case
    assert r.status_code == 409


def test_invalid_input_is_rejected(client):
    assert register(client, username="ab").status_code == 422           # too short
    assert register(client, username="bad name!").status_code == 422    # bad characters
    assert register(client, password="short").status_code == 422       # password too short


def test_unknown_fields_are_rejected(client):
    r = client.post(
        "/auth/register",
        json={"username": "alice", "password": "password123", "is_admin": True},
    )
    assert r.status_code == 422
