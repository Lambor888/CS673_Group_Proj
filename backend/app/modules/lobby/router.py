from fastapi import APIRouter, Depends, HTTPException, status

from app.modules.lobby.service import LobbyManager, Player, LobbyOut, Lobby, LobbyCreate, PlayerOut, ConnectionManager
from app.modules.auth.deps import get_current_user
from app.modules.auth.models import User
import uuid
from uuid import UUID
from typing import Annotated

router = APIRouter(prefix="/lobbies", tags=["lobbies"])

connection_manager = ConnectionManager()
lobby_manager = LobbyManager()
active_players = set()


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

def lobby_message(lobby: Lobby) -> dict:
    return {"type": "lobby_update", "data": output_lobby(lobby)} 

def chat_message(lobby:Lobby, user_id: int) -> dict:
    return {"type": "chat", "user": "Server", "text": "{} left the lobby.".format(user_id) }

async def leave_flow(player_id: int) -> None:
    lobby_id: UUID = lobby_manager.lobby_of(player_id)
    if lobby_id is None:
        return
    lobby = lobby_manager.lobbies.get(lobby_id)
    if lobby is None:
        return

    curr_player: Player = lobby.players[player_id]

    if player_id == lobby.host_id:
        lobby_manager.delete(lobby_id)
        await connection_manager.close_lobby(lobby_id, {"type": "lobby_closed"})
    else:
        lobby_manager.remove_player(lobby_id, player_id)
        await connection_manager.leave(player_id)
        await connection_manager.broadcast(lobby_id, lobby_message(lobby))
        await connection_manager.broadcast(lobby_id, chat_message(lobby, curr_player.username))

#lobby id is a uuid
@router.post("/createLobby", response_model=LobbyOut, status_code=201)
async def create_lobby(body: LobbyCreate, user: Annotated[User, Depends(get_current_user)]):
    await leave_flow(user.id)
    host = Player(user.id, user.username)
    print("User id: {}".format(user.id))
    curr_lobby = lobby_manager.create_lobby(host)
    print("Number of lobbies: {}".format(len(lobby_manager.lobbies)))
    curr_lobby.set_name(body.name.strip())
    return output_lobby(curr_lobby)

@router.get("/{lobby_id}", response_model=LobbyOut)
def get_lobby(lobby_id: str, user: Annotated[User, Depends(get_current_user)]):
    print(lobby_manager.lobbies)
    converted_string = uuid.UUID(lobby_id)
    lobby = lobby_manager.lobbies[converted_string]
    print("Lobby: {}".format(lobby.name))
    if lobby is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lobby not found")
    return output_lobby(lobby)

@router.post("/{lobby_id}/start")
async def start_game(lobby_id: UUID, user: Annotated[User, Depends(get_current_user)]):
    lobby = lobby_manager.lobbies.get(lobby_id)
    if lobby is None:
        raise HTTPException(status_code=404, detail="Lobby not found")
    if lobby.host_id != user.id:
        raise HTTPException(status_code=403, detail="Only the host can start the game")
    if lobby.num_players < 2:
        raise HTTPException(status_code=409, detail="Not enough players")
    await connection_manager.broadcast(lobby_id, {"type": "game_started"})

@router.post("/{lobby_code}/join", response_model=LobbyOut)
async def join_lobby(lobby_code: str, user: Annotated[User, Depends(get_current_user)]):
    await leave_flow(user.id)
    lobbies = lobby_manager.get_all_lobbies()
    curr_lobby = None
    for lobby in lobbies:
        if lobby.code == lobby_code:
            curr_lobby = lobby
            break
    if curr_lobby is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lobby not found")
    
    if user.id not in lobby.players:
        if lobby.is_full():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Lobby is full")
        p = Player(user.id, user.username)
        lobby.add_player(p)
    out = output_lobby(lobby)
    await connection_manager.broadcast(
        lobby.id, {"type": "lobby_update", "data": out.model_dump(mode="json")}
    )
    return out

@router.post("/{lobby_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
async def leave_lobby(lobby_id: str, user: Annotated[User, Depends(get_current_user)]):
    if lobby_manager.lobbies.get(UUID(lobby_id)) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lobby not found")
    await leave_flow(user.id)