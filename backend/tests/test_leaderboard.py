from sqlalchemy import select

from app.modules.auth.models import User, UserFriend
from app.modules.profile.models import GameHistory


def account(client, name):
    client.post("/auth/register", json={"username": name, "email": f"{name}@example.com", "password": "password123"})
    token = client.post("/auth/login", data={"username": name, "password": "password123"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def game(db, user_id, score, mode="single"):
    db.add(GameHistory(user_id=user_id, mode=mode, final_score=score, rounds_played=5, players=1, won=False))
    db.commit()


def setup(client, db):
    headers = {name: account(client, name) for name in ("alice", "bob", "carol")}
    ids = {u.username: u.id for u in db.scalars(select(User))}
    game(db, ids["alice"], 9000)
    game(db, ids["alice"], 12000)
    game(db, ids["bob"], 15000)
    game(db, ids["carol"], 11000)
    game(db, ids["carol"], 99999, mode="lobby")
    return headers, ids


def rows(response):
    assert response.status_code == 200
    return [(e["rank"], e["username"], e["best_score"], e["games"]) for e in response.json()]


def test_global_board_ranks_each_players_best_game(client, db_session):
    headers, _ = setup(client, db_session)
    assert rows(client.get("/profile/leaderboard", headers=headers["alice"])) == [
        (1, "bob", 15000, 1), (2, "alice", 12000, 2), (3, "carol", 11000, 1)]


def test_friends_board_shows_only_you_and_your_friends(client, db_session):
    headers, ids = setup(client, db_session)
    db_session.add(UserFriend(user_id=ids["alice"], friend_id=ids["carol"]))
    db_session.commit()
    assert rows(client.get("/profile/leaderboard?scope=friends", headers=headers["alice"])) == [
        (1, "alice", 12000, 2), (2, "carol", 11000, 1)]


def test_board_is_per_mode_and_needs_login(client, db_session):
    headers, _ = setup(client, db_session)
    assert rows(client.get("/profile/leaderboard?mode=lobby", headers=headers["bob"])) == [(1, "carol", 99999, 1)]
    assert client.get("/profile/leaderboard").status_code == 401
