from threading import Lock
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.modules.auth.deps import get_current_user
from app.modules.capfinder.service import CapitalGame, CapitalGameError

router = APIRouter(prefix='/capfinder', tags=['capital finder'])
games: dict[int, CapitalGame] = {}
games_lock = Lock()


class StartRound(BaseModel):
    model_config = ConfigDict(extra='forbid')
    previous_round_id: UUID | None = None


class Guess(BaseModel):
    model_config = ConfigDict(extra='forbid')
    lat: float = Field(ge=-90, le=90, allow_inf_nan=False)
    lng: float = Field(ge=-180, le=180, allow_inf_nan=False)


class State(BaseModel):
    round_id: UUID
    number: int
    country: str
    seconds_left: float
    finished: bool
    total_score: int
    score: int | None
    distance_km: float | None
    guess: Guess | None


def state(game: CapitalGame) -> State:
    current = game.current
    current.refresh()
    # Never expose the correct capital's name or coordinates to the browser.
    return State(round_id=current.id, number=current.number, country=current.location.country,
                 seconds_left=0 if current.finished else current.seconds_left(),
                 finished=current.finished, total_score=game.total_score,
                 score=current.score if current.finished else None,
                 distance_km=current.distance_km, guess=current.guess)


def find_game(user_id: int) -> CapitalGame:
    if user_id not in games:
        raise HTTPException(404, 'Start a capital finder game first.')
    return games[user_id]


@router.post('/round', response_model=State)
def start_round(body: StartRound, user=Depends(get_current_user)):
    with games_lock:
        game = games.get(user.id)
        if game is None:
            if body.previous_round_id is not None:
                raise HTTPException(409, 'Game expired. Start a new game.')
            game = games[user.id] = CapitalGame.start()
        elif body.previous_round_id is not None:
            try:
                game.next_round(body.previous_round_id)
            except CapitalGameError as exc:
                raise HTTPException(409, str(exc)) from None
        return state(game)


@router.get('', response_model=State)
def get_game(user=Depends(get_current_user)):
    with games_lock:
        return state(find_game(user.id))


@router.post('/round/{round_id}/guess', response_model=State)
def submit_guess(round_id: UUID, body: Guess, user=Depends(get_current_user)):
    with games_lock:
        game = find_game(user.id)
        try:
            game.submit(round_id, body.lat, body.lng)
        except CapitalGameError as exc:
            raise HTTPException(409, str(exc)) from None
        return state(game)
