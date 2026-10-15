import uuid
from pydantic import BaseModel, Field, field_validator
from uuid import UUID

class Entity:
    def __init__(self):
        self.id = uuid.uuid4()

    def get_id(self):
        return self.id

    def equals(self, ent):
        return self.id == ent.id

class Player(Entity):
    def __init__(self, p_id):
        super().__init__()
        self.p_id = p_id


class ConnectionManager(Entity):
    def __int__(self):
        self.sockets = {}

    def register_player(self, player, websocket):  #Assume that player is an object
        self.sockets[player.get_id] = websocket

    def unregister_player(self, player): #Assume that player is an object
        self.sockets.pop(player.get_id, None)

class LobbyManager(Entity):
    # Local, single-process storage; rooms disappear when the server restarts.
    def __init__(self):
        super().__init__()
        self.lobbies = {}

    def create_lobby(self, host):
        lobby = Lobby()
        lobby.initialize_lobby(host)
        self.lobbies[lobby.get_id()] = lobby
        return lobby

    def get_lobby(self, lobby_id):
        return self.lobbies.get(lobby_id)

    def get_all_lobbies(self):
        self.destroy_lobbies()
        return list(self.lobbies.values())

    def destroy_lobbies(self):
        for lobby_id, lobby in list(self.lobbies.items()):
            if lobby.flag:
                self.lobbies.pop(lobby_id)


class Lobby(Entity):
    def __init__(self):
        super().__init__()
        self.name = "Lobby {}".format(self.get_id())
        self.connections = {}
        self.players = {}
        self.host_id = None
        self.flag = False
        self.max_players = 5

    @property
    def num_players(self):
        return len(self.players)

    def initialize_lobby(self, host):
        self.host_id = host.p_id
        self.players[self.host_id] = host

    def add_player(self, player):
        if player.p_id in self.players:
            return
        if self.is_full():
            raise ValueError("Too many players")
        self.players[player.p_id] = player

    def is_full(self):
        return self.num_players >= self.max_players

    def remove_player(self, player_id):
        self.players.pop(player_id, None)
        if player_id == self.host_id:
            # Hand hosting to the first remaining player, or None if empty.
            self.host_id = next(iter(self.players), None)
        if not self.players:
            self.flag = True

    def set_name(self, lobby_name):
        self.name = lobby_name

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

class LobbyOut(BaseModel):
    id: UUID
    name: str
    player_ids: dict[int, PlayerOut]
    host_id: int
    num_players: int
    max_players: int
    flag: bool

