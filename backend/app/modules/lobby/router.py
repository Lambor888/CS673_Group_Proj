from fastapi import APIRouter, Depends, HTTPException, status

from app.modules.lobby.service import ConnectionManager, LobbyManager, Player, LobbyOut, Lobby, LobbyCreate, PlayerOut
from app.modules.auth.deps import get_current_user

router = APIRouter(prefix="/lobbies", tags=["lobbies"])

connection_manager = ConnectionManager()
lobby_manager = LobbyManager()
active_players = set()


@router.websocket("/ws")
async def websocket_ep(websocket):
    await websocket.accept()
    player = Player()
    active_players.add(player.get_id)
    connection_manager.register_player(player)

def output_lobby(lobby):
    return LobbyOut(
        id = lobby.get_id(),
        name = lobby.name,
        player_ids = {pid: PlayerOut(id=p.p_id) for pid, p in lobby.players.items()},
        host_id = lobby.host_id,
        num_players = lobby.num_players,
        max_players = lobby.max_players,
        flag = lobby.flag,
    ) 


@router.post("/createLobby", response_model=LobbyOut, status_code=201)
def create_lobby(body: LobbyCreate, user=Depends(get_current_user)):
    host = Player(user.id)
    print(user.id)
    curr_lobby = lobby_manager.create_lobby(host)
    curr_lobby.set_name(body.name.strip())
    return output_lobby(curr_lobby)

@router.get("/{lobby_id}", response_model=LobbyOut)
def get_lobby(lobby_id: str, user=Depends(get_current_user)):
    lobby = lobby_manager[lobby_id]
    if lobby is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lobby not found")
    return lobby

@router.post("/{lobby_id}/join", response_model=LobbyOut)
def join_lobby(lobby_id: str, user=Depends(get_current_user)):
    lobby = lobby_manager[lobby_id]
    if lobby is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lobby not found")
    if user.id not in lobby.players:
        if lobby.is_full():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Lobby is full")
        lobby.add_player(user)
    return output_lobby(lobby)

@router.post("/{lobby_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
def leave_lobby(lobby_id: str, user=Depends(get_current_user)):
    lobby = lobby_manager[lobby_id]
    if lobby is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lobby not found")
    lobby.remove_player(user.id)
    if not lobby.players:
        lobby.flag = True
        lobby_manager.destroy_lobbies()