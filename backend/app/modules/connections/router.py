import uuid

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.db import get_db
from app.modules.auth.deps import get_user_from_token
from app.modules.lobby import router as lobby_router
from app.modules.lobby.service import Player

# Read lobby_manager / connection_manager off the lobby router module at call time (not
# `from ... import lobby_manager`), so this always sees the same objects the lobby
# endpoints use, including when tests swap them out.

router = APIRouter(prefix="/ws", tags=["ws"])

# Close codes the frontend acts on (4000-4999 are free for applications).
# A client must not reconnect after one of these; any other drop is retried.
CLOSE_NOT_A_MEMBER = 4401  # bad token, unknown lobby, or no longer in it


async def reject(ws: WebSocket, code: int) -> None:
    # Closing before accept() turns into an HTTP 403 and browsers only ever see code 1006,
    # which looks like a network drop. Accept first so the client gets the real code.
    await ws.accept()
    await ws.close(code=code)


@router.websocket("/{lobby_id}")
async def lobby_ws(ws: WebSocket, lobby_id: str, token: str, db: Session = Depends(get_db)):
    user = get_user_from_token(token, db)
    db.close()
    if user is None:
        await reject(ws, CLOSE_NOT_A_MEMBER)
        return

    player = Player(user.id, user.username)
    try:
        room_id = uuid.UUID(lobby_id)
    except ValueError:
        await reject(ws, CLOSE_NOT_A_MEMBER)
        return

    lobby_manager = lobby_router.lobby_manager
    connection_manager = lobby_router.connection_manager
    lobby = lobby_manager.lobbies.get(room_id)
    if lobby is None or player.p_id not in lobby.players:
        await reject(ws, CLOSE_NOT_A_MEMBER)
        return

    await connection_manager.connect(player.p_id, room_id, ws)
    await connection_manager.send(player.p_id, lobby_router.lobby_message(lobby))

    try:
        while True:
            msg = await ws.receive_json()
            if msg.get("type") == "chat":
                text = str(msg.get("text", "")).strip()[:200]
                if text:
                    await connection_manager.broadcast(
                        room_id,
                        {"type": "chat", "user": player.username, "text": text},
                    )
    except WebSocketDisconnect:
        pass
    finally:
        # A closed socket is not a leave: refreshing, going from the lobby to the game page,
        # or a network blip all close it. Keep the seat for a grace period and only remove
        # the player if they haven't reconnected by then. Explicit leaves use POST /leave.
        if connection_manager.disconnect(player.p_id, ws):
            lobby_router.schedule_disconnect_leave(player.p_id, room_id)
