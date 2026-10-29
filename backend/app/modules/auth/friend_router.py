from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Response, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.modules.auth import friends
from app.modules.auth.deps import get_current_user, get_user_from_token
from app.modules.auth.models import User, UserFriend
from app.modules.auth.notifications import notifications
from app.modules.auth.schemas import FriendRequestCreate, FriendRequestOut, UserOut

router = APIRouter(tags=["friends"])


@router.get("/friends", response_model=list[UserOut])
def list_friends(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(select(User).join(UserFriend, UserFriend.friend_id == User.id)
                      .where(UserFriend.user_id == user.id).order_by(User.id)).all()


@router.post("/friend-requests", response_model=FriendRequestOut, status_code=201)
async def send_friend_request(body: FriendRequestCreate, user: User = Depends(get_current_user),
                              db: Session = Depends(get_db)):
    result = friends.send_request(db, user.id, body.recipient_id)
    await notifications.send(result.recipient_id, {
        "type": "friend_request", "data": result.model_dump(mode="json")
    })
    return result


@router.get("/friend-requests/pending", response_model=list[FriendRequestOut])
def list_pending(direction: Literal["incoming", "outgoing"] = "incoming",
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return friends.pending_requests(db, user.id, direction)


async def respond_and_notify(db: Session, request_id: UUID, user_id: int, decision: str):
    result = friends.respond(db, str(request_id), user_id, decision)
    message = {"type": "friend_request_updated", "data": result.model_dump(mode="json")}
    await notifications.send(result.sender_id, message)
    await notifications.send(result.recipient_id, message)
    return result


@router.post("/friend-requests/{request_id}/accept", response_model=FriendRequestOut)
async def accept_request(request_id: UUID, user: User = Depends(get_current_user),
                         db: Session = Depends(get_db)):
    return await respond_and_notify(db, request_id, user.id, "accepted")


@router.post("/friend-requests/{request_id}/reject", response_model=FriendRequestOut)
async def reject_request(request_id: UUID, user: User = Depends(get_current_user),
                         db: Session = Depends(get_db)):
    return await respond_and_notify(db, request_id, user.id, "rejected")


@router.delete("/friends/{friend_id}", status_code=204)
async def delete_friend(friend_id: int, user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    user_id = user.id
    if friends.remove_friend(db, user_id, friend_id):
        await notifications.send(user_id, {"type": "friend_removed", "data": {"friend_id": friend_id}})
        await notifications.send(friend_id, {"type": "friend_removed", "data": {"friend_id": user_id}})
    return Response(status_code=204)


@router.websocket("/notifications/ws")
async def account_socket(ws: WebSocket, token: str, db: Session = Depends(get_db)):
    user = get_user_from_token(token, db)
    if user is None:
        await ws.close(code=4401)
        return
    user_id = user.id
    pending = friends.pending_requests(db, user_id)
    # Release the database transaction while keeping the notification socket open.
    db.rollback()
    await ws.accept()
    notifications.add(user_id, ws)
    try:
        await ws.send_json({"type": "friend_requests_pending", "data": [
            request.model_dump(mode="json") for request in pending
        ]})
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        notifications.remove(user_id, ws)
