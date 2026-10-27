from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.profile.models import RoundResult


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
