from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# What the client sends. FastAPI rejects anything else with a 422.
class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")  # unknown fields (typos, "is_admin") -> 422

    username: str = Field(min_length=3, max_length=20, pattern=r"^[A-Za-z0-9_]+$")
    password: str = Field(min_length=8, max_length=128)


# What the API sends back. No password_hash here, ever.
class UserOut(BaseModel):
    id: int
    username: str


# What /auth/login returns.
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class FriendRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recipient_id: int = Field(gt=0)


class FriendRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    sender_id: int
    recipient_id: int
    status: Literal["pending", "accepted", "rejected", "removed"]
    created_at: datetime
