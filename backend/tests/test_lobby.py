import uuid
from app.modules.lobby.service import Entity, Player, ConnectionManager, LobbyManager, Lobby
import asyncio
import unittest
def test_entity_ids():
    assert Player(0, "p0").get_id() != Player(0, "p0").get_id()
    assert Lobby().get_id() != Lobby().get_id()
    assert Entity().get_id() != Entity().get_id()

def test_lobby_is_not_empty():
    manager = LobbyManager()
    player = Player(0, "p0")
    lobby = manager.create_lobby(player)
    assert lobby.num_players == 1
    assert len(lobby.players) == 1


def test_n_players():
    manager = LobbyManager()
    host = Player(0, "p0")
    p1 = Player(1, "p1")
    p2 = Player(2, "p2")
    lobby = manager.create_lobby(host)
    lobby.add_player(p1)
    lobby.add_player(p2)

    assert len(lobby.players) == 3

def test_max_players():
    manager = LobbyManager()
    host = Player(0, "p0")
    lobby = manager.create_lobby(host)
    for i in range(1,5):
        p = Player(i, f"p{i}")
        lobby.add_player(p)

    assert len(lobby.players) == 5


def test_send_to_unknown_player_is_a_no_op():
    # Regression: send() used to read conn.player_id before checking conn for None.
    manager = ConnectionManager()
    asyncio.run(manager.send(123, {"type": "chat", "text": "hi"}))
    asyncio.run(manager.broadcast(uuid.uuid4(), {"type": "lobby_update"}))
