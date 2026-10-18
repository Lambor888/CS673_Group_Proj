import uuid
from pydantic import BaseModel, Field
from uuid import UUID
import secrets
import string
import websockets

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
        self.p_id = p_id
        self.username = name


class LobbyManager(Entity):
    def __init__(self):
        super().__init__()
        self.lobbies = {}
        

    def create_lobby(self, host):
        lobby = Lobby()
        lobby.initialize_lobby(host)
        self.lobbies[lobby.id] = lobby
        return lobby

    def get_all_lobbies(self):
        self.destroy_lobbies()
        return list(self.lobbies.values())

    def destroy_lobbies(self):
        for key, lobby in self.lobbies.items():
            if lobby.flag == True:
                self.lobbies.pop(key, None)

        
        


class Lobby(Entity):
    valid_characters = string.ascii_uppercase + string.digits
    def __init__(self):
        super().__init__()
        self.name = "Lobby {}".format(self.get_id())
        self.connections = {}
        self.players = {}
        self.host_id = None
        self.flag = False
        self.num_players = 1
        self.max_players = 5
        self.code = self.generate_lobby_code(6)

    def generate_lobby_code(self, length):
        return ''.join(secrets.choice(Lobby.valid_characters) for _ in range(length))

    def initialize_lobby(self, host):
        self.host_id = host.p_id
        self.players[self.host_id] = host
    
    def add_player(self, player): 
        if self.num_players < self.max_players:
            p = player.p_id
            self.players[p] = player
        else:
            raise Exception("Too many players")

    def is_full(self):
        return self.num_players >= self.max_players

    def remove_player(self, player):
        p= player.p_id
        self.players.pop(p)
        if not self.players:
            self.flag = True

    def set_name(self, lobby_name):
        self.name = lobby_name

class LobbyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=20)

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

