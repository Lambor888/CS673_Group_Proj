"""HTTP endpoints for round-based games. All the rules live in service.py, all the points in app/scoring.py."""
from contextlib import contextmanager
from threading import Lock
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.modules.auth.deps import get_current_user
from app.modules.lobby.router import lobby_lock, lobby_manager
from app.modules.location.service import Location, LocationError, generate_location
from app.modules.rounds.service import (
    GameError, GameRound, LobbyGame, PlayerGuess, SinglePlayerGame,
)
from app.scoring import haversine_distance

router = APIRouter(prefix="/games", tags=["games"])


# ---- Request / response models ---------------------------------------------
class Guess(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lat: float = Field(ge=-90, le=90, allow_inf_nan=False)
    lng: float = Field(ge=-180, le=180, allow_inf_nan=False)


class NextRound(BaseModel):
    model_config = ConfigDict(extra="forbid")
    previous_round: int = Field(ge=1)


class Point(BaseModel):
    lat: float
    lng: float


class PlayerResultOut(BaseModel):
    guessed: bool                      # False if the timer ran out first
    lat: float | None
    lng: float | None
    distance_km: float | None
    score: int | None = None           # single player: points earned this round
    penalty: int | None = None         # lobby: points lost this round


class RoundOut(BaseModel):
    number: int
    total_rounds: int | None           # None for lobby games: they last until one player is left
    multiplier: float                  # lobby penalty multiplier for this round
    seconds_left: float
    finished: bool
    pano_id: str                       # the browser only gets this until the round is over
    submitted: list[int]               # user ids that have guessed so far
    answer: Point | None               # revealed once the round is finished
    results: dict[int, PlayerResultOut] | None  # filled once the round is finished


class GameOut(BaseModel):
    mode: str                          # "single" or "lobby"
    over: bool
    winner: int | None
    active_players: list[int]
    eliminated_players: list[int]
    total_score: int | None = None     # single player: running total
    round_scores: list[int] | None = None  # single player: points per finished round
    points: dict[int, int] | None = None   # lobby: points left per player
    current_round: RoundOut


# ---- Helpers ----------------------------------------------------------------
def new_location(previous_pano: str | None) -> Location:
    try:
        return generate_location(previous_pano)
    except LocationError as exc:
        raise HTTPException(503, str(exc)) from None


@contextmanager
def rule_errors():
    """Turn a broken game rule into an HTTP 409."""
    try:
        yield
    except GameError as exc:
        raise HTTPException(409, str(exc)) from None


def to_player_guess(game_round: GameRound, body: Guess) -> PlayerGuess:
    loc = game_round.location
    distance = haversine_distance(loc.lat, loc.lng, body.lat, body.lng)
    return PlayerGuess(lat=body.lat, lng=body.lng, distance_km=round(distance, 3))


def round_out(game_round: GameRound, total_rounds: int | None) -> RoundOut:
    answer = None
    results = None
    if game_round.finished:
        answer = Point(lat=game_round.location.lat, lng=game_round.location.lng)
        results = {}
        for pid, g in game_round.results().items():
            results[pid] = PlayerResultOut(
                guessed=g is not None,
                lat=g.lat if g else None,
                lng=g.lng if g else None,
                distance_km=g.distance_km if g else None,
                score=game_round.scores.get(pid),
                penalty=game_round.penalties.get(pid),
            )
    return RoundOut(
        number=game_round.number,
        total_rounds=total_rounds,
        multiplier=game_round.multiplier,
        seconds_left=round(game_round.seconds_left(), 2),
        finished=game_round.finished,
        pano_id=game_round.location.pano_id,
        submitted=sorted(game_round.guesses),
        answer=answer,
        results=results,
    )


# ---- Single player ----------------------------------------------------------
# Development storage: one game per user, in memory. Single worker only.
single_games: dict[int, SinglePlayerGame] = {}
single_lock = Lock()


def single_out(game: SinglePlayerGame) -> GameOut:
    return GameOut(
        mode="single", over=game.over, winner=None,
        active_players=[game.user_id], eliminated_players=[],
        total_score=game.total_score, round_scores=game.round_scores,
        current_round=round_out(game.current, game.total_rounds),
    )


def find_single(user) -> SinglePlayerGame:
    game = single_games.get(user.id)
    if game is None:
        raise HTTPException(404, "No game in progress. Start one first.")
    game.refresh()
    return game


@router.post("/single", response_model=GameOut)
def start_single_game(user=Depends(get_current_user)):
    """Start a new 5-round game. If one is still in progress, return it instead."""
    with single_lock:
        game = single_games.get(user.id)
        if game is not None:
            game.refresh()
            if not game.over:
                return single_out(game)
        game = SinglePlayerGame.start(user.id, new_location)
        single_games[user.id] = game
        return single_out(game)


@router.get("/single", response_model=GameOut)
def get_single_game(user=Depends(get_current_user)):
    with single_lock:
        return single_out(find_single(user))


@router.post("/single/guess", response_model=GameOut)
def single_guess(body: Guess, user=Depends(get_current_user)):
    with single_lock:
        game = find_single(user)
        with rule_errors():
            game.guess(user.id, to_player_guess(game.current, body))
        return single_out(game)


@router.post("/single/next", response_model=GameOut)
def single_next_round(body: NextRound, user=Depends(get_current_user)):
    with single_lock:
        game = find_single(user)
        with rule_errors():
            game.start_next(body.previous_round, new_location)
        return single_out(game)


# ---- Lobby ------------------------------------------------------------------
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


@router.post("/lobby/{lobby_id}/start", response_model=GameOut)
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


@router.get("/lobby/{lobby_id}", response_model=GameOut)
def get_lobby_game(lobby_id: UUID, user=Depends(get_current_user)):
    """Poll this to see the timer, who has guessed, points, and when the round is over."""
    with lobby_games_lock:
        return lobby_out(find_lobby_game(lobby_id, user))


@router.post("/lobby/{lobby_id}/guess", response_model=GameOut)
def lobby_guess(lobby_id: UUID, body: Guess, user=Depends(get_current_user)):
    with lobby_games_lock:
        game = find_lobby_game(lobby_id, user)
        with rule_errors():
            game.guess(user.id, to_player_guess(game.current, body))
        return lobby_out(game)


@router.post("/lobby/{lobby_id}/next", response_model=GameOut)
def lobby_next_round(lobby_id: UUID, body: NextRound, user=Depends(get_current_user)):
    """Any remaining player can call this once a round is over; extra calls return the same new round."""
    with lobby_games_lock:
        game = find_lobby_game(lobby_id, user)
        with rule_errors():
            game.start_next(body.previous_round, new_location)
        return lobby_out(game)
