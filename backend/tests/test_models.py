import pytest
from sqlalchemy.exc import IntegrityError

from app.models import User


def test_user_roundtrip(db_session):
    db_session.add(User(username="alice", password_hash="x"))
    db_session.commit()

    user = db_session.query(User).filter_by(username="alice").one()
    assert user.id is not None
    assert user.created_at is not None


def test_username_is_unique(db_session):
    db_session.add(User(username="bob", password_hash="x"))
    db_session.commit()

    db_session.add(User(username="bob", password_hash="y"))
    with pytest.raises(IntegrityError):
        db_session.commit()
