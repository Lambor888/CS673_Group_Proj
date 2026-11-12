import pytest
from sqlalchemy import select

from app.modules.auth.models import User
from app.modules.flags import router as flags
from app.modules.profile.models import GameHistory


@pytest.fixture(autouse=True)
def fresh_games():
    flags.games.clear()


def account(client, name="alice"):
    client.post("/auth/register", json={"username": name, "email": f"{name}@example.com", "password": "password123"})
    token = client.post("/auth/login", data={"username": name, "password": "password123"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_a_question_has_four_countries_and_one_is_right(client):
    headers = account(client)
    q = client.post("/flags/question", headers=headers).json()
    answer = next(g["country"] for g in flags.games.values() if g["id"] == q["id"])
    assert len(set(q["options"])) == 4 and answer in q["options"]
    assert q["flag_url"].startswith("https://flagcdn.com/")


def test_wrong_answer_tells_the_country_and_each_flag_is_answered_once(client):
    headers = account(client)
    q = client.post("/flags/question", headers=headers).json()
    right = next(g["country"] for g in flags.games.values() if g["id"] == q["id"])
    wrong = next(c for c in q["options"] if c != right)
    r = client.post("/flags/answer", headers=headers, json={"id": q["id"], "country": wrong}).json()
    assert r == {"correct": False, "country": right, "score": 0, "done": False}
    assert client.post("/flags/answer", headers=headers, json={"id": q["id"], "country": right}).status_code == 404


def test_a_finished_game_is_saved_for_the_leaderboard(client, db_session):
    headers = account(client)
    for _ in range(flags.FLAGS_PER_GAME):
        q = client.post("/flags/question", headers=headers).json()
        right = next(g["country"] for g in flags.games.values() if g["id"] == q["id"])
        r = client.post("/flags/answer", headers=headers, json={"id": q["id"], "country": right}).json()
    assert r == {"correct": True, "country": right, "score": 10, "done": True}
    user = db_session.scalar(select(User).where(User.username == "alice"))
    saved = db_session.scalar(select(GameHistory).where(GameHistory.user_id == user.id))
    assert (saved.mode, saved.final_score, saved.rounds_played) == ("flags", 10, 10)
