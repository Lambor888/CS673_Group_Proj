import uuid
from app.modules.lobby.service import Entity, Player, ConnectionManager, LobbyManager, Lobby
import unittest
def test_entity_ids():
    assert Player().get_id() != Player().get_id()
    assert Lobby().get_id() != Lobby().get_id()
    assert Entity().get_id() != Entity().get_id()

def test_lobby_is_not_empty():
    manager = LobbyManager()
    player = Player()
    lobby = manager.create_lobby(player)
    assert lobby.num_players == 1
    assert len(lobby.players) == 1


def test_n_players():
    manager = LobbyManager()
    host = Player()
    p1 = Player()
    p2 = Player()
    lobby = manager.create_lobby(host)
    lobby.add_player(p1)
    lobby.add_player(p2)

    assert len(lobby.players) == 3

def test_max_players():
    manager = LobbyManager()
    host = Player()
    lobby = manager.create_lobby(host)
    for _ in range(4):
        p = Player()
        lobby.add_player(p)

    assert len(lobby.players) == 5
