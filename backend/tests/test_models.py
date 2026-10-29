import pytest
from sqlalchemy.exc import IntegrityError

from app.modules.auth.models import User, UserFriend


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


def test_friend_ids_roundtrip_and_remove(db_session):
    alice, bob, carol = [User(username=name, password_hash="x")
                         for name in ("alice", "bob", "carol")]
    db_session.add_all([alice, bob, carol])
    db_session.commit()
    assert list(alice.friend_ids) == []
    alice.friend_ids = [bob.id, carol.id]
    db_session.commit()
    db_session.expire_all()
    assert set(alice.friend_ids) == {bob.id, carol.id}
    assert list(bob.friend_ids) == []
    alice.friend_ids.remove(bob.id)
    db_session.commit()
    db_session.expire_all()
    assert list(alice.friend_ids) == [carol.id]


@pytest.mark.parametrize("invalid", ["self", "missing", "duplicate"])
def test_invalid_friend_ids_rejected(db_session, invalid):
    alice = User(username="alice", password_hash="x")
    bob = User(username="bob", password_hash="x")
    db_session.add_all([alice, bob])
    db_session.commit()
    alice.friend_ids = {
        "self": [alice.id], "missing": [999999], "duplicate": [bob.id, bob.id]
    }[invalid]
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_deleting_user_cleans_incoming_and_outgoing_friendships(db_session):
    alice = User(username="alice", password_hash="x")
    bob = User(username="bob", password_hash="x")
    db_session.add_all([alice, bob])
    db_session.commit()
    alice.friend_ids = [bob.id]
    bob.friend_ids = [alice.id]
    db_session.commit()
    db_session.expire_all()
    db_session.delete(bob)
    db_session.commit()
    db_session.expire_all()
    assert list(alice.friend_ids) == []
    assert db_session.query(UserFriend).count() == 0
