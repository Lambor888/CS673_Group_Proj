from threading import Lock
from uuid import UUID

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
# Sync endpoints run in threads; keep each room update and response together.
lobby_lock = Lock()
active_players = set()

# How long a player whose socket dropped (refresh, lobby -> game page, network blip)
# keeps their seat before being removed from the lobby.
DISCONNECT_GRACE_SECONDS = 15.0


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
    # Leaving on purpose (or joining/creating another room) supersedes any pending disconnect leave.
    connection_manager.cancel_pending_leave(player_id)
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

def schedule_disconnect_leave(player_id: int, lobby_id: UUID) -> None:
    """A player's socket closed: remove them from `lobby_id` unless they reconnect within the grace period."""
    async def leave_if_still_gone():
        if player_id in connection_manager.active_players:
            return  # back online
        if lobby_manager.lobby_of(player_id) != lobby_id:
            return  # already left, or moved to another room
        await leave_flow(player_id)

    connection_manager.schedule_leave(player_id, leave_if_still_gone, DISCONNECT_GRACE_SECONDS)

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
def get_lobby(lobby_id: UUID, user: Annotated[User, Depends(get_current_user)]):
    # UUID path type: malformed ids get 422, unknown ids fall through to 404 below.
    lobby = lobby_manager.lobbies.get(lobby_id)
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
    # Find the target room before touching the player's current one, so a bad code,
    # a full room, or re-joining the room you're already in never kicks you out
    # (and a host re-joining their own code doesn't delete their room).
    lobby = next(
        (room for room in lobby_manager.get_all_lobbies() if room.code == lobby_code), None
    )
    if lobby is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lobby not found")

    if user.id not in lobby.players:
        if lobby.is_full():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Lobby is full")
        # Only now leave whatever room the player was in before.
        await leave_flow(user.id)
        # leave_flow awaits websocket sends, so re-check the room survived and still has space.
        if lobby_manager.lobbies.get(lobby.id) is not lobby:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lobby not found")
        if lobby.is_full():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Lobby is full")
        lobby.add_player(Player(user.id, user.username))
    out = output_lobby(lobby)
    await connection_manager.broadcast(
        lobby.id, {"type": "lobby_update", "data": out.model_dump(mode="json")}
    )
    return out

@router.post("/{lobby_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
async def leave_lobby(lobby_id: UUID, user: Annotated[User, Depends(get_current_user)]):
    lobby = lobby_manager.lobbies.get(lobby_id)
    if lobby is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lobby not found")
    # Leave *this* room only; a non-member (or a member of another room) is a no-op.
    if user.id in lobby.players:
        await leave_flow(user.id)
