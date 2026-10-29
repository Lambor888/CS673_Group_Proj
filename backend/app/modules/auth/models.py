from datetime import datetime

from sqlalchemy import String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    # Stored lowercase. Optional only because accounts made before emails existed have none.
    email: Mapped[str | None] = mapped_column(String(254), unique=True, index=True)
    # None for accounts that only sign in with Google.
    password_hash: Mapped[str | None] = mapped_column(String(255))
    # Google's stable account id ("sub"), set once the account is connected to Google.
    google_sub: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
