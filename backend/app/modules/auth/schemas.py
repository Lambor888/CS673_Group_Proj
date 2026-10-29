from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

Username = Annotated[str, Field(min_length=3, max_length=20, pattern=r"^[A-Za-z0-9_]+$")]
Password = Annotated[str, Field(min_length=8, max_length=128)]


# What the client sends. FastAPI rejects anything else with a 422.
class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")  # unknown fields (typos, "is_admin") -> 422

    username: Username
    email: Annotated[EmailStr, Field(max_length=254)]
    password: Password

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, email: str) -> str:
        return email.lower()  # "Bob@Mail.com" and "bob@mail.com" are the same account


# Someone else's account, as other players see it. No email, no password_hash, ever.
class UserOut(BaseModel):
    id: int
    username: str


# Your own account (register, /auth/me, profile). Still never the password hash.
class AccountOut(BaseModel):
    id: int
    username: str
    email: str | None
    has_password: bool  # False for accounts that only sign in with Google
    google_connected: bool
    created_at: datetime


# What /auth/login returns.
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class GoogleToken(Token):
    new_account: bool  # True the first time someone signs in with Google


class GoogleCredential(BaseModel):
    model_config = ConfigDict(extra="forbid")
    credential: str = Field(min_length=1, max_length=8192)  # ID token from the Google button


class UsernameChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: Username


class PasswordChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str | None = Field(default=None, max_length=128)  # not needed to set a first password
    new_password: Password


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
