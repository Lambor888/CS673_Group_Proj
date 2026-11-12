from typing import Literal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.modules.auth.deps import get_current_user
from app.modules.auth.models import User, UserFriend
from app.modules.profile.service import HistoryEntry, LeaderboardEntry, Stats, history_for, leaderboard, stats_for

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("/stats", response_model=Stats)
def my_stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return stats_for(db, user.id)

@router.get("/history", response_model=list[HistoryEntry])
def my_history(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Finished games, newest first (single player and multiplayer)."""
    return history_for(db, user.id)


@router.get("/leaderboard", response_model=list[LeaderboardEntry])
def get_leaderboard(mode: str = "single", scope: Literal["global", "friends"] = "global",
                    user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Best score per player. scope=friends shows only you and your friends."""
    ids = None
    if scope == "friends":
        ids = [user.id, *db.scalars(select(UserFriend.friend_id).where(UserFriend.user_id == user.id))]
    return leaderboard(db, mode, ids)
