"""Both previously deployed migration branches must upgrade without losing data."""
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from app.config import settings


@pytest.mark.parametrize("start", ["base", "d4e819a62b30", "4139cc94314c"])
def test_upgrade_both_branches_preserves_data(tmp_path, monkeypatch, start):
    backend = Path(__file__).resolve().parents[1]
    url = f"sqlite:///{tmp_path / 'migration.db'}"
    monkeypatch.setattr(settings, "database_url", url)
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "migrations"))
    command.upgrade(config, start)
    engine = create_engine(url)
    try:
        if start != "base":
            with engine.begin() as connection:
                connection.execute(text("INSERT INTO users (id, username, password_hash) VALUES (1, 'alice', 'hash'), (2, 'bob', 'hash')"))
                if start == "d4e819a62b30":
                    connection.execute(text("INSERT INTO user_friends (user_id, friend_id) VALUES (1, 2), (2, 1)"))
                    connection.execute(text("INSERT INTO friend_requests (id, user_low_id, user_high_id, sender_id, recipient_id, status) VALUES ('existing-request', 1, 2, 1, 2, 'accepted')"))
                    connection.execute(text("INSERT INTO revoked_tokens (token_hash) VALUES ('existing-hash')"))
                else:
                    connection.execute(text("UPDATE users SET email='alice@example.com', google_sub='google-alice' WHERE id=1"))
                    connection.execute(text("INSERT INTO round_results (user_id, mode, score, distance_km) VALUES (1, 'single', 5000, 0)"))
        command.upgrade(config, "head")
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "e2710f49b6c2"
            assert not connection.exec_driver_sql("PRAGMA foreign_key_check").all()
            assert set(inspect(connection).get_table_names()) >= {
                "users", "user_friends", "friend_requests", "revoked_tokens", "round_results"
            }
            if start != "base":
                assert connection.scalar(text("SELECT count(*) FROM users")) == 2
            if start == "d4e819a62b30":
                assert connection.scalar(text("SELECT count(*) FROM user_friends")) == 2
                assert connection.scalar(text("SELECT status FROM friend_requests")) == "accepted"
                assert connection.scalar(text("SELECT count(*) FROM revoked_tokens")) == 1
            if start == "4139cc94314c":
                assert connection.scalar(text("SELECT google_sub FROM users WHERE id=1")) == "google-alice"
                assert connection.scalar(text("SELECT score FROM round_results")) == 5000
    finally:
        engine.dispose()
