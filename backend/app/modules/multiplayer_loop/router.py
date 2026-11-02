"""
Same idea as modules/singlePlayer, but one game belongs to a whole lobby: everyone in the room guesses the
same location, the closest guess keeps its points, and the others lose points until one player is left.
The rules live in rounds/service.py (LobbyGame), the points in app/scoring.py, the room itself in modules/lobby.
"""
from threading import Lock
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal, get_db
from app.modules.auth.deps import get_current_user
from app.modules.auth.models import User
from app.modules.lobby import router as lobby_router
from app.modules.lobby.router import lobby_lock, lobby_manager
from app.modules.profile.models import GameHistory
from app.modules.rounds.router import (
    FinalResultOut, GameOut, Guess, NextRound, new_location, round_out, rule_errors, to_player_guess,)
from app.modules.rounds.service import LobbyGame

router = APIRouter(prefix="/games/lobby", tags=["multiplayer"])

#one game per lobby
lobby_games: dict[UUID, LobbyGame] = {}
lobby_games_lock = Lock()  #when both locks are needed, always take lobby_lock first

def open_session() -> Session:
    return SessionLocal()

def lobby_out(game: LobbyGame, db: Session) -> GameOut:
    final = None
    if game.over:
        names = {u.id: u.username for u in db.scalars(select(User).where(User.id.in_(list(game.points))))}
        final = [FinalResultOut(player_id=pid, username=names.get(pid, f"Player {pid}"), rank=rank, final_score=pts)
                 for pid, rank, pts in game.standings()]
    return GameOut(
        mode="lobby", over=game.over, winner=game.winner,
        active_players=sorted(game.active), eliminated_players=sorted(game.eliminated),
        points=dict(game.points), final_results=final,
        current_round=round_out(game.current, None),
    )


def save_history_once(game: LobbyGame, db: Session) -> None:
    if not game.over or game.history_saved:
        return
    try:
        for player_id, rank, final_points in game.standings():
            db.add(GameHistory(user_id=player_id, mode="lobby", final_score=final_points,
                               rounds_played=len(game.rounds), players=len(game.points),
                               placement=rank, won=(player_id == game.winner)))
        db.commit()
    except Exception:
        db.rollback()
        raise
    game.history_saved = True


def lobby_state(game: LobbyGame, db: Session) -> GameOut:
    save_history_once(game, db)     
    return lobby_out(game, db)

def find_lobby_game(lobby_id: UUID, user) -> LobbyGame:
    game = lobby_games.get(lobby_id)
    if game is None:
        raise HTTPException(404, "No game in progress in this lobby.")
    if user.id not in game.points or user.id in game.departed:
        raise HTTPException(403, "You are not part of this game.")
    game.refresh()
    return game


@router.post("/{lobby_id}/start", response_model=GameOut)
def start_lobby_game(lobby_id: UUID, user=Depends(get_current_user), db: Session = Depends(get_db)):
    with lobby_lock, lobby_games_lock:
        lobby = lobby_manager.lobbies.get(lobby_id)
        if lobby is None:
            raise HTTPException(404, "Lobby not found")
        if lobby.host_id != user.id:
            raise HTTPException(403, "Only the host can start the game.")
        existing = lobby_games.get(lobby_id)
        if existing is not None:
            existing.refresh()
            save_history_once(existing, db)
            if not existing.over:
                return lobby_state(existing, db)
        with rule_errors():
            game = LobbyGame.start(lobby_id, set(lobby.players), new_location)
        lobby_games[lobby_id] = game
        return lobby_out(game, db)


@router.get("/{lobby_id}", response_model=GameOut)
def get_lobby_game(lobby_id: UUID, user=Depends(get_current_user), db : Session = Depends(get_db)):
    with lobby_games_lock:
        return lobby_state(find_lobby_game(lobby_id, user), db)


@router.post("/{lobby_id}/guess", response_model=GameOut)
def lobby_guess(lobby_id: UUID, body: Guess, user=Depends(get_current_user), db: Session = Depends(get_db)):
    with lobby_games_lock:
        game = find_lobby_game(lobby_id, user)
        with rule_errors():
            game.guess(user.id, to_player_guess(game.current, body))
        return lobby_state(game, db)


@router.post("/{lobby_id}/next", response_model=GameOut)
def lobby_next_round(lobby_id: UUID, body: NextRound, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Any remaining player can call this once a round is over; extra calls return the same new round."""
    with lobby_games_lock:
        game = find_lobby_game(lobby_id, user)
        save_history_once(game, db)
        if user.id not in game.active:
            raise HTTPException(409, "Only active players can advance the round.")
        with rule_errors():
            game.start_next(body.previous_round, new_location)
        return lobby_out(game, db)


def drop_player_from_game(lobby_id: UUID, player_id: int, lobby_closed: bool) -> None:
    """Keeps the game in step with the lobby. Registered with the lobby router below."""
    with lobby_games_lock:
        if lobby_closed:
            lobby_games.pop(lobby_id, None) 
            return
        game = lobby_games.get(lobby_id)
        if game is None:
            return
        game.remove_player(player_id)
        if game.over and not game.history_saved:
            db = open_session()
            try:
                save_history_once(game, db)
            finally:
                db.close()


lobby_router.player_left_hooks.append(drop_player_from_game)
