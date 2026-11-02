"""HTTP endpoints for round-based games. All the rules live in service.py, all the points in app/scoring.py."""
from contextlib import contextmanager
from threading import Lock
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.modules.auth.deps import get_current_user
from app.modules.profile.models import GameHistory, RoundResult
from app.modules.location.service import Location, LocationError, generate_location
from app.modules.rounds.service import (
    GameError, GameRound, PlayerGuess, SinglePlayerGame,
)
from app.scoring import haversine_distance

router = APIRouter(prefix="/games", tags=["games"])


# ---- Request / response models ---------------------------------------------
class Guess(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lat: float = Field(ge=-90, le=90, allow_inf_nan=False)
    lng: float = Field(ge=-180, le=180, allow_inf_nan=False)
    round_id: UUID | None = None


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
    round_id: UUID
    number: int
    total_rounds: int | None           # None for lobby games: they last until one player is left
    multiplier: float                  # lobby penalty multiplier for this round
    seconds_left: float
    finished: bool
    pano_id: str                       # the browser only gets this until the round is over
    submitted: list[int]               # user ids that have guessed so far
    answer: Point | None               # revealed once the round is finished
    results: dict[int, PlayerResultOut] | None  # filled once the round is finished


class FinalResultOut(BaseModel):
    player_id: int
    username: str
    rank: int
    final_score: int


class GameOut(BaseModel):
    final_results: list[FinalResultOut] | None = None
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
def new_location(used_panos: set[str]) -> Location:
    try:
        return generate_location(used_panos)
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
    if body.round_id is not None and body.round_id != game_round.id:
        raise HTTPException(409, "Round changed. Reload the current round before submitting.")
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
        round_id=game_round.id,
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


def single_out(game: SinglePlayerGame, db: Session) -> GameOut:
    unsaved = [r for r in game.rounds if r.scored and r.number not in game.saved_rounds]
    save_game = game.over and not game.history_saved
    try:
        for r in unsaved:
            guess = r.guesses.get(game.user_id)
            if guess:
                db.add(RoundResult(user_id=game.user_id, mode="single",
                                   score=r.scores[game.user_id], distance_km=guess.distance_km))
        if save_game:
            db.add(GameHistory(user_id=game.user_id, mode="single", final_score=game.total_score,
                               rounds_played=len(game.rounds), players=1, placement=None, won=False))
        if unsaved or save_game:
            db.commit()
    except Exception:
        db.rollback()
        raise
    game.saved_rounds.update(r.number for r in unsaved)
    if save_game:
        game.history_saved = True
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
def start_single_game(user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Start a new 5-round game. If one is still in progress, return it instead."""
    with single_lock:
        game = single_games.get(user.id)
        if game is not None:
            game.refresh()
            single_out(game, db)
            if not game.over:
                return single_out(game, db)
        game = SinglePlayerGame.start(user.id, new_location)
        single_games[user.id] = game
        return single_out(game, db)


@router.get("/single", response_model=GameOut)
def get_single_game(user=Depends(get_current_user), db: Session = Depends(get_db)):
    with single_lock:
        return single_out(find_single(user), db)


@router.post("/single/guess", response_model=GameOut)
def single_guess(body: Guess, user=Depends(get_current_user), db: Session = Depends(get_db)):
    with single_lock:
        game = find_single(user)
        with rule_errors():
            game.guess(user.id, to_player_guess(game.current, body))
        return single_out(game, db)


@router.post("/single/next", response_model=GameOut)
def single_next_round(body: NextRound, user=Depends(get_current_user), db: Session = Depends(get_db)):
    with single_lock:
        game = find_single(user)
        single_out(game, db)
        with rule_errors():
            game.start_next(body.previous_round, new_location)
        return single_out(game, db)
