import uuid
from pydantic import BaseModel, Field, field_validator
from fastapi.encoders import jsonable_encoder
from uuid import UUID
import secrets
import string
from fastapi import WebSocket
from typing import Annotated
import traceback
from starlette.websockets import WebSocketState

class Entity:
    def __init__(self):
        self.id = uuid.uuid4()

    def get_id(self):
        return self.id

    def equals(self, ent):
        return self.id == ent.id

class Player(Entity):
    def __init__(self, p_id, name):
        super().__init__()
        self.p_id: int = p_id
        self.username: str = name

class Lobby(Entity):
    valid_characters = string.ascii_uppercase + string.digits
    def __init__(self):
        super().__init__()
        self.name = "Lobby {}".format(self.get_id())
        self.connections = {}
        self.players: dict[int, Player] = {}
        self.host_id: int | None = None
        self.flag: bool = False
        self.max_players: int = 5
        self.code: str = self.generate_lobby_code(6)

    @property
    def num_players(self) -> int:
        return len(self.players)

    def generate_lobby_code(self, length: int) -> str:
        return ''.join(secrets.choice(Lobby.valid_characters) for _ in range(length))

    def initialize_lobby(self, host: Player) -> None:
        self.host_id: int = host.p_id
        self.players[self.host_id] = host
    
    def add_player(self, player: Player) -> None: 
        if self.num_players < self.max_players:
            p = player.p_id
            self.players[p] = player
        else:
            raise Exception("Too many players")

    def is_full(self) -> bool:
        return self.num_players >= self.max_players

    def remove_player(self, player_id: int) -> None:
        return self.players.pop(player_id, None) is not None

    def set_name(self, lobby_name: str) -> None:
        self.name = lobby_name

class LobbyManager(Entity):
    # Local, single-process storage; rooms disappear when the server restarts.
    def __init__(self):
        super().__init__()
        self.lobbies: dict[UUID, Lobby] = {}
        

    def create_lobby(self, host: Player) -> Lobby:
        lobby = Lobby()
        lobby.initialize_lobby(host)
        self.lobbies[lobby.id] = lobby
        return lobby

    def get_all_lobbies(self) -> list[Lobby]:
        self.destroy_lobbies()
        return list(self.lobbies.values())

    def destroy_lobbies(self) -> None:
        for key, lobby in list(self.lobbies.items()):
            if lobby.flag == True:
                self.lobbies.pop(key, None)

    def lobby_of(self, p_id: int) -> UUID | None:
        lobby_lst: list[Lobby] = self.get_all_lobbies()
        for lobby in lobby_lst:
            if p_id in list(lobby.players.keys()):
                return lobby.id
        return None

    def delete(self, lobby_id: UUID) -> None:
        self.lobbies.pop(lobby_id, None)

    def remove_player(self, lobby_id: UUID, player_id: int):
        curr_lobby = self.lobbies.get(lobby_id)
        if curr_lobby:
            curr_lobby.remove_player(player_id)

class PlayerConnection(Entity):
    def __init__(self, player_id, lobby_id, websocket):
        super().__init__()
        self.player_id = player_id
        self.lobby_id = lobby_id
        self.websocket = websocket

class ConnectionManager(Entity):
    def __init__(self):
        super().__init__()
        self.active_players: dict[int, PlayerConnection] = {}
        self.lobby_members: dict[UUID, set[int]] = {}

    async def connect(self, player_id, lobby_id, websocket):
        await websocket.accept()
        old_connection = self.active_players.get(player_id)
        if old_connection is not None:
            self.discard_member(old_connection.lobby_id, player_id)
            self.active_players[player_id] = PlayerConnection(player_id, lobby_id, websocket)
            await self.close_connection(old_connection.websocket)
        else:
            self.active_players[player_id] = PlayerConnection(player_id, lobby_id, websocket)

        print("Num active players: {}".format(self.active_players))
        self.lobby_members.setdefault(lobby_id, set()).add(player_id)
        print("Lobby members: {}".format(self.lobby_members[lobby_id]))

    def disconnect(self, player_id, websocket=None) -> bool:
        conn = self.active_players.get(player_id)
        if conn is None:
            return False
        if websocket is not None and conn.websocket is not websocket:
            return False
        self.active_players.pop(player_id, None)
        self.discard_member(conn.lobby_id, player_id)
        return True

    async def leave(self, player_id):
        conn = self.active_players.get(player_id)
        if conn is None:
            return
        self.disconnect(player_id)
        await self.close_connection(conn.websocket)

    async def send(self, player_id, message):
        conn = self.active_players.get(player_id)
        print("{} : {}".format(conn.player_id, conn.lobby_id))
        if conn is None or conn.websocket is None:
            return
        ws = conn.websocket
        if ws.client_state != WebSocketState.CONNECTED or ws.application_state != WebSocketState.CONNECTED:
            self.disconnect(player_id, ws)
            return
        payload = jsonable_encoder(message)

        try:
            await ws.send_json(payload)
        except Exception:
            traceback.print_exc()
            self.disconnect(player_id)

    async def broadcast(self, lobby_id, message):
        print("broadcast", lobby_id, self.lobby_members.get(lobby_id))
        copy = list(self.lobby_members.get(lobby_id, []))
        for player_id in copy:
            await self.send(player_id, message)

    async def close_lobby(self, lobby_id, message: dict) -> None:
        copy = list(self.lobby_members.get(lobby_id, []))
        print(copy)
        for player_id in copy:
            await self.send(player_id, message)
            conn = self.active_players.pop(player_id, None)
            if conn is not None:
                await self.close_connection(conn.websocket)
        self.lobby_members.pop(lobby_id, None)

    def discard_member(self, lobby_id, player_id):
        current_members = self.lobby_members.get(lobby_id)
        if current_members is not None:
            current_members.discard(player_id)
            if not current_members:
                self.lobby_members.pop(lobby_id, None)

    async def close_connection(self, ws, code=1000):
        #code 1000 in fastapi means a normal closure
        try:
            await ws.close(code=code)
        except Exception:
            pass

class LobbyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=20)

    @field_validator("name")
    @classmethod
    def trim_name(cls, name):
        name = name.strip()
        if not name:
            raise ValueError("Lobby name cannot be blank")
        return name

class PlayerOut(BaseModel):
    id: int
    name: str

class LobbyOut(BaseModel):
    id: UUID
    name: str
    player_ids: dict[int, PlayerOut]
    host_id: int
    num_players: int
    max_players: int
    flag: bool
    code: str

