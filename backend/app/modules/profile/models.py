from datetime import datetime

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, func
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
    """A completed game, mapped to the existing game_history migration."""

    __tablename__ = "game_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    mode: Mapped[str] = mapped_column(String(20))
    final_score: Mapped[int] = mapped_column(Integer)
    rounds_played: Mapped[int] = mapped_column(Integer)
    players: Mapped[int] = mapped_column(Integer)
    placement: Mapped[int | None] = mapped_column(Integer, nullable=True)
    won: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

