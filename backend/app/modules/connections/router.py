from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect

from app.modules.lobby.service import ConnectionManager, PlayerConnection, Player, LobbyOut, PlayerOut
from app.modules.lobby.router import lobby_manager, connection_manager, leave_flow
from app.modules.auth.deps import get_current_user, get_user_from_token
import uuid
from app.db import get_db
from uuid import UUID
from sqlalchemy.orm import Session


router = APIRouter(prefix="/ws", tags=["ws"])


def output_lobby(lobby):
    return LobbyOut(
        id = lobby.get_id(),
        name = lobby.name,
        player_ids = {pid: PlayerOut(id=p.p_id, name=p.username) for pid, p in lobby.players.items()},
        host_id = lobby.host_id,
        num_players = lobby.num_players,
        max_players = lobby.max_players,
        flag = lobby.flag,
        code = lobby.code
    ) 



@router.websocket("/{lobby_id}")
async def lobby_ws(ws: WebSocket, lobby_id: str, token: str, db: Session = Depends(get_db)):
    
    print("ws endpoint hit")
    user = get_user_from_token(token, db)
    if user is None:
        await ws.close(code=4401)
        return
    
    player = Player(user.id, user.username)
    db.close()
    lobby_id = uuid.UUID(lobby_id)
    lobby = lobby_manager.lobbies.get(lobby_id)
    
    if lobby is None or player.p_id not in lobby.players:
        await ws.close(code=4401)
        return

    await connection_manager.connect(player.p_id, lobby_id, ws)
    lobby_out = output_lobby(lobby_manager.lobbies[lobby_id])
    await connection_manager.send(player.p_id, {"type": "lobby_update", "data": lobby_out})

    try:
        while True:
            msg = await ws.receive_json()
            if msg.get("type") == "chat":
                text = str(msg.get("text", "")).strip()[:200]
                if text:
                    await connection_manager.broadcast(
                        lobby_id,
                        {"type": "chat", "user": player.username, "text": text},
                    )
    except WebSocketDisconnect:
        pass
    finally:
        if connection_manager.disconnect(player.p_id, ws):
            await leave_flow(player.p_id)
    