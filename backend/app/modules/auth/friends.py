"""Transactional friendship operations. Only acceptance creates friendship links."""
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import and_, delete, or_, select, update, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.auth.models import FriendRequest, User, UserFriend
from app.modules.auth.schemas import FriendRequestOut


def pair_filter(user_id: int, friend_id: int):
    return and_(FriendRequest.user_low_id == min(user_id, friend_id),
                FriendRequest.user_high_id == max(user_id, friend_id))


def links_filter(user_id: int, friend_id: int):
    return or_(and_(UserFriend.user_id == user_id, UserFriend.friend_id == friend_id),
               and_(UserFriend.user_id == friend_id, UserFriend.friend_id == user_id))


def pending_requests(db: Session, user_id: int, direction: str = "incoming"):
    owner = FriendRequest.recipient_id if direction == "incoming" else FriendRequest.sender_id
    return [FriendRequestOut.model_validate(item) for item in db.scalars(
        select(FriendRequest).where(owner == user_id, FriendRequest.status == "pending")
        .order_by(FriendRequest.created_at, FriendRequest.id)
    )]


def send_request(db: Session, sender_id: int, recipient_id: int):
    if sender_id == recipient_id:
        raise HTTPException(400, "You cannot add yourself")
    if db.get(User, recipient_id) is None:
        raise HTTPException(404, "User not found")
    if db.scalar(select(UserFriend).where(links_filter(sender_id, recipient_id))):
        raise HTTPException(409, "Already friends")
    existing = db.scalar(select(FriendRequest).where(pair_filter(sender_id, recipient_id)))
    if existing and existing.status in ("pending", "accepted"):
        raise HTTPException(409, "A friend request already exists for these users")
    try:
        if existing:
            # A new ID prevents a delayed response to an old request accepting a new one.
            request_id = str(uuid4())
            changed = db.execute(update(FriendRequest).where(
                FriendRequest.id == existing.id,
                FriendRequest.status.in_(["rejected", "removed"]),
            ).values(id=request_id, sender_id=sender_id, recipient_id=recipient_id,
                     status="pending", created_at=func.now()))
            if changed.rowcount != 1:
                db.rollback()
                raise HTTPException(409, "Friend request changed; refresh and try again")
        else:
            request_id = str(uuid4())
            db.add(FriendRequest(id=request_id, sender_id=sender_id, recipient_id=recipient_id,
                                user_low_id=min(sender_id, recipient_id),
                                user_high_id=max(sender_id, recipient_id), status="pending"))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Friend request conflicts with an existing request")
    db.expire_all()
    return FriendRequestOut.model_validate(db.get(FriendRequest, request_id))


def respond(db: Session, request_id: str, user_id: int, decision: str):
    request = db.get(FriendRequest, request_id)
    if request is None or request.recipient_id != user_id:
        raise HTTPException(404, "Friend request not found")
    if request.status == decision:
        return FriendRequestOut.model_validate(request)
    if request.status != "pending":
        raise HTTPException(409, "Friend request is no longer pending")
    sender_id, recipient_id = request.sender_id, request.recipient_id
    changed = db.execute(update(FriendRequest).where(
        FriendRequest.id == request_id, FriendRequest.status == "pending",
        FriendRequest.recipient_id == user_id,
    ).values(status=decision))
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Friend request changed; refresh and try again")
    if decision == "accepted":
        db.add_all([UserFriend(user_id=sender_id, friend_id=recipient_id),
                    UserFriend(user_id=recipient_id, friend_id=sender_id)])
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Friendship changed; refresh and try again")
    db.expire_all()
    return FriendRequestOut.model_validate(db.get(FriendRequest, request_id))


def remove_friend(db: Session, user_id: int, friend_id: int):
    # Update the pair first to serialize removal against acceptance/re-request.
    db.execute(update(FriendRequest).where(
        pair_filter(user_id, friend_id), FriendRequest.status == "accepted"
    ).values(status="removed"))
    removed = db.execute(delete(UserFriend).where(links_filter(user_id, friend_id)))
    db.commit()
    return removed.rowcount > 0
