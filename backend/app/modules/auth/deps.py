from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.modules.auth.models import RevokedToken, User
from app.modules.auth.security import decode_access_token, token_digest

# Reads "Authorization: Bearer <token>" and powers the Authorize button in /docs.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_user_from_token(token: str, db: Session) -> User | None:
    user_id = decode_access_token(token)
    if user_id is None or db.get(RevokedToken, token_digest(token)) is not None:
        return None
    return db.get(User, user_id)


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    user = get_user_from_token(token, db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not logged in",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
