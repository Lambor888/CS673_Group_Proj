from datetime import datetime
from uuid import uuid4

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.ext.associationproxy import AssociationProxy, association_proxy
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    # Stored lowercase. Optional only because accounts made before emails existed have none.
    email: Mapped[str | None] = mapped_column(String(254), unique=True, index=True)
    # None for accounts that only sign in with Google.
    password_hash: Mapped[str | None] = mapped_column(String(255))
    # Google's stable account id ("sub"), set once the account is connected to Google.
    google_sub: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    friend_links: Mapped[list["UserFriend"]] = relationship(
        foreign_keys="UserFriend.user_id",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    # Each user's list is stored independently; reciprocal friendship is a service concern.
    friend_ids: AssociationProxy[list[int]] = association_proxy(
        "friend_links", "friend_id", creator=lambda friend_id: UserFriend(friend_id=friend_id)
    )


class UserFriend(Base):
    __tablename__ = "user_friends"
    __table_args__ = (
        CheckConstraint("user_id <> friend_id", name="ck_user_friends_not_self"),
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    friend_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )


class FriendRequest(Base):
    __tablename__ = "friend_requests"
    __table_args__ = (
        UniqueConstraint("user_low_id", "user_high_id", name="uq_friend_requests_pair"),
        CheckConstraint("user_low_id < user_high_id", name="ck_friend_requests_pair"),
        CheckConstraint(
            "(sender_id = user_low_id AND recipient_id = user_high_id) OR "
            "(sender_id = user_high_id AND recipient_id = user_low_id)",
            name="ck_friend_requests_participants",
        ),
        CheckConstraint("status IN ('pending', 'accepted', 'rejected', 'removed')",
                        name="ck_friend_requests_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_low_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    user_high_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    recipient_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(10), default="pending")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class RevokedToken(Base):
    __tablename__ = "revoked_tokens"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    revoked_at: Mapped[datetime] = mapped_column(server_default=func.now())
