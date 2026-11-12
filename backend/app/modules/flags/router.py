"""Flag matcher: show a flag, pick its country from four. Ten flags a game; finished games go to the leaderboard."""
import random
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.modules.auth.deps import get_current_user
from app.modules.auth.models import User
from app.modules.location.service import CAPITALS
from app.modules.profile.service import record_game

router = APIRouter(prefix="/flags", tags=["flag matcher"])
FLAGS_PER_GAME = 10
games: dict[int, dict] = {}  # user id -> current game, in memory like capital finder


class Question(BaseModel):
    id: str
    number: int
    score: int
    flag_url: str
    options: list[str]


class Answer(BaseModel):
    id: str
    country: str


class Result(BaseModel):
    correct: bool
    country: str
    score: int
    done: bool


@router.post("/question", response_model=Question)
def next_question(user: User = Depends(get_current_user)):
    game = games.get(user.id)
    if game is None or game["number"] >= FLAGS_PER_GAME:
        game = games[user.id] = {"number": 0, "score": 0}
    picks = random.sample(CAPITALS, 4)
    game.update(id=str(uuid4()), country=picks[0].country, number=game["number"] + 1)
    options = [c.country for c in picks]
    random.shuffle(options)
    return Question(id=game["id"], number=game["number"], score=game["score"],
                    flag_url=f"https://flagcdn.com/w320/{picks[0].code.lower()}.png", options=options)


@router.post("/answer", response_model=Result)
def answer(body: Answer, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    game = games.get(user.id)
    if game is None or game.get("id") != body.id:
        raise HTTPException(404, "No such question.")
    game["id"] = None  # one answer per flag
    correct = body.country == game["country"]
    game["score"] += int(correct)
    done = game["number"] >= FLAGS_PER_GAME
    if done:
        record_game(db, user.id, "flags", game["score"], FLAGS_PER_GAME)
    return Result(correct=correct, country=game["country"], score=game["score"], done=done)
