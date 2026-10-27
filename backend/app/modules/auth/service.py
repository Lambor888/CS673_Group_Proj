import re
import secrets

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.auth.google import GoogleIdentity
from app.modules.auth.models import User
from app.modules.auth.schemas import AccountOut


class AccountConflict(Exception):
    """A unique field (username, email, Google account) is already used by someone else."""


def account_out(user: User) -> AccountOut:
    return AccountOut(
        id=user.id,
        username=user.username,
        email=user.email,
        has_password=user.password_hash is not None,
        google_connected=user.google_sub is not None,
        created_at=user.created_at,
    )


def find_login_user(db: Session, identifier: str) -> User | None:
    """The login form takes a username or an email."""
    identifier = identifier.strip().lower()
    if "@" in identifier:
        return db.query(User).filter_by(email=identifier).first()
    return db.query(User).filter_by(username=identifier).first()


def username_taken(db: Session, username: str) -> bool:
    return db.query(User.id).filter_by(username=username).first() is not None


def email_taken(db: Session, email: str) -> bool:
    return db.query(User.id).filter_by(email=email).first() is not None


def username_from_google(db: Session, identity: GoogleIdentity) -> str:
    """A free username based on the Google email ("Jane.Doe@gmail.com" -> "jane_doe").

    Players can change it on their profile afterwards.
    """
    base = re.sub(r"[^a-z0-9_]+", "_", identity.email.split("@")[0].lower()).strip("_")[:15]
    if len(base) < 3:
        base = f"player_{base}".rstrip("_")
    if not username_taken(db, base):
        return base
    for _ in range(20):
        candidate = f"{base}_{secrets.randbelow(10_000):04d}"
        if not username_taken(db, candidate):
            return candidate
    return f"player_{secrets.token_hex(6)}"  # 19 chars; practically never reached


def create_google_user(db: Session, identity: GoogleIdentity) -> User:
    if email_taken(db, identity.email):
        raise AccountConflict(
            "An account with this email already exists. Log in with your password, "
            "then connect Google from your profile."
        )
    user = User(
        username=username_from_google(db, identity),
        email=identity.email,
        password_hash=None,
        google_sub=identity.sub,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # Someone took the same username/email at the same moment (or a double click).
        db.rollback()
        existing = db.query(User).filter_by(google_sub=identity.sub).first()
        if existing is not None:
            return existing
        raise AccountConflict("Couldn't create your account. Please try again.") from None
    db.refresh(user)
    return user


def link_google(db: Session, user: User, identity: GoogleIdentity) -> User:
    if user.google_sub == identity.sub:
        return user  # already connected
    if user.google_sub is not None:
        raise AccountConflict("Your account is already connected to a different Google account.")
    if db.query(User.id).filter_by(google_sub=identity.sub).first() is not None:
        raise AccountConflict("That Google account is already used by another player.")
    user.google_sub = identity.sub
    if user.email is None and not email_taken(db, identity.email):
        user.email = identity.email  # older accounts made before emails existed
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AccountConflict("That Google account is already used by another player.") from None
    db.refresh(user)
    return user
