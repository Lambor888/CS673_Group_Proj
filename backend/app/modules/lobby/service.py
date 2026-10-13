import uuid


class Entity:
    def __init__(self):
        self.id = uuid.uuid4()

    def get_id(self):
        return self.id

    def equals(self, ent):
        return self.id == ent.id

class Player(Entity):
    def __init__(self):
        super().__init__()


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
        lobby.add_player(host)
        lobby_id = self.get_id()
        self.lobbies[lobby_id] = False
        return lobby

    def get_all_lobies(self):
        self.destroy_lobbies()
        return list(self.lobbies.values())

    def destroy_lobbies(self):
        for lobby, deletion_flag in self.lobbies.items():
            if deletion_flag == True:
                self.lobbies.pop(lobby, None)

        
        


class Lobby(Entity):
    def __init__(self):
        super().__init__()
        self.connections = {}
        self.players = {}
        self.flag = False
        self.num_players = 1
        self.max_players = 5
    
    def add_player(self, player):
        if len(self.players) < self.max_players:
            p_id = player.get_id()
            self.players[p_id] = player
        else:
            raise Exception("Too many players")

    def remove_player(self, player):
        p_id = player.get_id()
        self.players.pop(player.get_id())
        if not self.players:
            self.flag = True

