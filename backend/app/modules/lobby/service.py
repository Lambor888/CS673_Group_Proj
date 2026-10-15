import uuid
from pydantic import BaseModel, Field
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
    def __init__(self):
        super().__init__()
        self.lobbies = {}
        

    def create_lobby(self, host):
        lobby = Lobby()
        lobby.initialize_lobby(host)
        lobby_id = self.get_id()
        self.lobbies[lobby_id] = False
        return lobby

    def get_all_lobbies(self):
        self.destroy_lobbies()
        return list(self.lobbies.values())

    def destroy_lobbies(self):
        for lobby, deletion_flag in self.lobbies.items():
            if deletion_flag == True:
                self.lobbies.pop(lobby, None)

        
        


class Lobby(Entity):
    def __init__(self):
        super().__init__()
        self.name = "Lobby {}".format(self.get_id())
        self.connections = {}
        self.players = {}
        self.host_id = None
        self.flag = False
        self.num_players = 1
        self.max_players = 5

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

class LobbyOut(BaseModel):
    id: UUID
    name: str
    player_ids: dict[int, PlayerOut]
    host_id: int
    num_players: int
    max_players: int
    flag: bool

