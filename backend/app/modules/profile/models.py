from datetime import datetime

from sqlalchemy import Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class RoundResult(Base):
    """One scored round a player finished. Profile stats are computed from these."""

    __tablename__ = "round_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    mode: Mapped[str] = mapped_column(String(20))  # "single" for now; lobby games later
    score: Mapped[int] = mapped_column(Integer)
    distance_km: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

class GameHistory(Base):
    """One finished game for one player: single player (5 rounds) or a lobby game (last player standing)."""

    __tablename__ = "game_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    mode: Mapped[str] = mapped_column(String(20))  # "single" or "lobby"
    final_score: Mapped[int] = mapped_column(Integer)  # single: total points, lobby: points left at the end
    rounds_played: Mapped[int] = mapped_column(Integer)
    players: Mapped[int] = mapped_column(Integer, default=1)
    placement: Mapped[int | None] = mapped_column(Integer, nullable=True)  # lobby only: 1 = first place
    won: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())