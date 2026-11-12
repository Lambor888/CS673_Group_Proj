from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from datetime import datetime
from app.modules.auth.models import User
from app.modules.profile.models import RoundResult, GameHistory


class Stats(BaseModel):
    rounds_played: int
    total_score: int
    best_score: int | None
    average_score: float | None
    best_distance_km: float | None
    average_distance_km: float | None


def record_round(db: Session, user_id: int, mode: str, score: int, distance_km: float) -> None:
    """Save a finished round. Call it once per scored guess, from any game mode."""
    db.add(RoundResult(user_id=user_id, mode=mode, score=score, distance_km=distance_km))
    db.commit()


def stats_for(db: Session, user_id: int) -> Stats:
    count, total, best, avg, closest, avg_km = db.execute(
        select(
            func.count(RoundResult.id),
            func.coalesce(func.sum(RoundResult.score), 0),
            func.max(RoundResult.score),
            func.avg(RoundResult.score),
            func.min(RoundResult.distance_km),
            func.avg(RoundResult.distance_km),
        ).where(RoundResult.user_id == user_id)
    ).one()
    return Stats(
        rounds_played=count,
        total_score=total,
        best_score=best,
        average_score=round(avg, 1) if avg is not None else None,
        best_distance_km=round(closest, 3) if closest is not None else None,
        average_distance_km=round(avg_km, 3) if avg_km is not None else None,
    )


class HistoryEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    mode: str
    final_score: int
    rounds_played: int
    players: int
    placement: int | None
    won: bool
    created_at: datetime


def record_game(db: Session, user_id: int, mode: str, final_score: int, rounds_played: int,
                players: int = 1, placement: int | None = None, won: bool = False) -> None:
    db.add(GameHistory(user_id=user_id, mode=mode, final_score=final_score, rounds_played=rounds_played,
                       players=players, placement=placement, won=won))
    db.commit()


def history_for(db: Session, user_id: int, limit: int = 20) -> list[GameHistory]:
    return list(db.scalars(
        select(GameHistory).where(GameHistory.user_id == user_id)
        .order_by(GameHistory.created_at.desc(), GameHistory.id.desc()).limit(limit)
    ))

class LeaderboardEntry(BaseModel):
    rank: int
    username: str
    best_score: int
    games: int


def leaderboard(db: Session, mode: str = "single", user_ids: list[int] | None = None,
                limit: int = 50) -> list[LeaderboardEntry]:
    """Each player's best final score in a mode, highest first. user_ids limits it (friends board)."""
    best = func.max(GameHistory.final_score)
    query = (select(User.username, best, func.count(GameHistory.id))
             .join(User, User.id == GameHistory.user_id)
             .where(GameHistory.mode == mode)
             .group_by(User.id, User.username)
             .order_by(best.desc(), User.username)
             .limit(limit))
    if user_ids is not None:
        query = query.where(GameHistory.user_id.in_(user_ids))
    return [LeaderboardEntry(rank=rank, username=name, best_score=score, games=games)
            for rank, (name, score, games) in enumerate(db.execute(query), start=1)]
