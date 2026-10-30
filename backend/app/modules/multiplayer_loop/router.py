"""
Same idea as modules/singlePlayer, but one game belongs to a whole lobby: everyone in the room guesses the
same location, the closest guess keeps its points, and the others lose points until one player is left.
The rules live in rounds/service.py (LobbyGame), the points in app/scoring.py, the room itself in modules/lobby.
"""
from threading import Lock
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.modules.auth.deps import get_current_user
from app.modules.lobby import router as lobby_router
from app.modules.lobby.router import lobby_lock, lobby_manager
from app.modules.rounds.router import GameOut, Guess, NextRound, new_location, round_out, rule_errors, to_player_guess
from app.modules.rounds.service import LobbyGame

router = APIRouter(prefix="/games/lobby", tags=["multiplayer"])

# Development storage: one game per lobby, in memory. Single worker only.
lobby_games: dict[UUID, LobbyGame] = {}
lobby_games_lock = Lock()  # when both locks are needed, always take lobby_lock first


def lobby_out(game: LobbyGame) -> GameOut:
    return GameOut(
        mode="lobby", over=game.over, winner=game.winner,
        active_players=sorted(game.active), eliminated_players=sorted(game.eliminated),
        points=dict(game.points),
        current_round=round_out(game.current, None),
    )


def find_lobby_game(lobby_id: UUID, user) -> LobbyGame:
    game = lobby_games.get(lobby_id)
    if game is None:
        raise HTTPException(404, "No game in progress in this lobby.")
    if user.id not in game.points:
        raise HTTPException(403, "You are not part of this game.")
    game.refresh()
    return game


@router.post("/{lobby_id}/start", response_model=GameOut)
def start_lobby_game(lobby_id: UUID, user=Depends(get_current_user)):
    """Host only. Everyone currently in the lobby plays; repeating the call returns the running game."""
    with lobby_lock, lobby_games_lock:
        lobby = lobby_manager.lobbies.get(lobby_id)
        if lobby is None:
            raise HTTPException(404, "Lobby not found")
        if lobby.host_id != user.id:
            raise HTTPException(403, "Only the host can start the game.")
        existing = lobby_games.get(lobby_id)
        if existing is not None:
            existing.refresh()
            if not existing.over:
                return lobby_out(existing)
        with rule_errors():
            game = LobbyGame.start(lobby_id, set(lobby.players), new_location)
        lobby_games[lobby_id] = game
        return lobby_out(game)


@router.get("/{lobby_id}", response_model=GameOut)
def get_lobby_game(lobby_id: UUID, user=Depends(get_current_user)):
    """Poll this to see the timer, who has guessed, points, and when the round is over."""
    with lobby_games_lock:
        return lobby_out(find_lobby_game(lobby_id, user))


@router.post("/{lobby_id}/guess", response_model=GameOut)
def lobby_guess(lobby_id: UUID, body: Guess, user=Depends(get_current_user)):
    with lobby_games_lock:
        game = find_lobby_game(lobby_id, user)
        with rule_errors():
            game.guess(user.id, to_player_guess(game.current, body))
        return lobby_out(game)


@router.post("/{lobby_id}/next", response_model=GameOut)
def lobby_next_round(lobby_id: UUID, body: NextRound, user=Depends(get_current_user)):
    """Any remaining player can call this once a round is over; extra calls return the same new round."""
    with lobby_games_lock:
        game = find_lobby_game(lobby_id, user)
        with rule_errors():
            game.start_next(body.previous_round, new_location)
        return lobby_out(game)


def drop_player_from_game(lobby_id: UUID, player_id: int, lobby_closed: bool) -> None:
    """Keeps the game in step with the lobby. Registered with the lobby router below."""
    with lobby_games_lock:
        if lobby_closed:
            lobby_games.pop(lobby_id, None)   # the host left, so the room and its game are gone
            return
        game = lobby_games.get(lobby_id)
        if game is not None:
            game.remove_player(player_id)


lobby_router.player_left_hooks.append(drop_player_from_game)
