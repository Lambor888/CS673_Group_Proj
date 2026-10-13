from fastapi import APIRouter

from app.modules.lobby.service import ConnectionManager, LobbyManager, Player

router = APIRouter()

connection_manager = ConnectionManager()
lobby_manager = LobbyManager()
active_players = set()


@router.websocket("/ws")
async def websocket_ep(websocket):
    await websocket.accept()
    player = Player()
    active_players.add(player.get_id)
    connection_manager.register_player(player)

