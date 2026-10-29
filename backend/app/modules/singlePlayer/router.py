from dataclasses import dataclass, field
from threading import Lock
from time import monotonic
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.modules.auth.deps import get_current_user
from app.modules.profile.service import record_round
from app.modules.location.service import Location, LocationError, generate_location
from app.scoring import haversine_distance, single_player_round_score

router = APIRouter(prefix="/singleplayer", tags=["singleplayer"])


class StartRound(BaseModel):
    model_config = ConfigDict(extra="forbid")
    previous_round_id: UUID | None = None


class Guess(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lat: float = Field(ge=-90, le=90, allow_inf_nan=False)
    lng: float = Field(ge=-180, le=180, allow_inf_nan=False)


class Point(BaseModel):
    lat: float
    lng: float


class Result(BaseModel):
    distance_km: float
    score: int
    guess: Guess
    answer: Point  # Revealed only after the guess is scored.


class RoundOut(BaseModel):
    # Only the panorama id goes to the browser before the guess, so the answer
    # isn't sitting in the API response. Street View needs nothing else.
    round_id: UUID
    pano_id: str
    result: Result | None = None


@dataclass
class Round:
    location: Location
    previous_id: UUID | None = None
    id: UUID = field(default_factory=uuid4)
    result: Result | None = None
    created_at: float = field(default_factory=monotonic)

    def output(self):
        return RoundOut(round_id=self.id, pano_id=self.location.pano_id, result=self.result)


# Development storage: one round per user, expires after two hours. Single worker only.
rounds: dict[int, Round] = {}
round_lock = Lock()


@router.post("/round", response_model=RoundOut)
def start_round(body: StartRound, user=Depends(get_current_user)):
    # Serializes duplicate requests, including React StrictMode's initial effect.
    with round_lock:
        for user_id, item in list(rounds.items()):
            if monotonic() - item.created_at > 7200:
                del rounds[user_id]
        current = rounds.get(user.id)
        if body.previous_round_id is None and current:
            return current.output()
        if body.previous_round_id is not None:
            if current and current.previous_id == body.previous_round_id:
                return current.output()  # Retry after a lost next-round response.
            if not current or current.id != body.previous_round_id:
                raise HTTPException(409, "Round expired or changed. Reload the page.")
            if current.result is None:
                raise HTTPException(409, "Submit your guess before starting the next round.")
        try:
            location = generate_location(current.location.pano_id if current else None)
        except LocationError as exc:
            raise HTTPException(503, str(exc)) from None
        new_round = Round(location=location, previous_id=body.previous_round_id)
        rounds[user.id] = new_round
        return new_round.output()


@router.post("/round/{round_id}/guess", response_model=Result)
def submit_guess(round_id: UUID, body: Guess, user=Depends(get_current_user), db: Session = Depends(get_db)):
    newly_scored = False
    with round_lock:
        current = rounds.get(user.id)
        if not current or current.id != round_id or monotonic() - current.created_at > 7200:
            raise HTTPException(404, "Round not found or expired. Reload the page.")
        if current.result is None:
            location = current.location
            distance = round(haversine_distance(location.lat, location.lng, body.lat, body.lng), 3)
            current.result = Result(
                distance_km=distance,
                score=single_player_round_score(distance),
                guess=body,
                answer=Point(lat=location.lat, lng=location.lng),
            )
            newly_scored = True
        result = current.result
    if newly_scored:  # a retried guess request doesn't count twice
        record_round(db, user.id, "single", result.score, result.distance_km)
    return result
