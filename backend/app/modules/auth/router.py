from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.modules.auth import google
from app.modules.auth.deps import get_current_user, oauth2_scheme
from app.modules.auth.friend_router import router as friend_router
from app.modules.auth.models import User, RevokedToken
from app.modules.auth.schemas import (
    AccountOut,
    GoogleCredential,
    GoogleToken,
    PasswordChange,
    Token,
    UserCreate,
    UsernameChange,
)
from app.modules.auth.security import DUMMY_HASH, create_access_token, hash_password, verify_password, token_digest
from app.modules.auth.service import (
    AccountConflict,
    account_out,
    create_google_user,
    email_taken,
    find_login_user,
    link_google,
    username_taken,
)

router = APIRouter(prefix="/auth", tags=["auth"])
router.include_router(friend_router)


@router.post("/register", response_model=AccountOut, status_code=201)
def register(body: UserCreate, db: Session = Depends(get_db)):
    username = body.username.lower()  # "Bob" and "bob" are the same account
    if username_taken(db, username):
        raise HTTPException(status_code=409, detail="Username already taken")
    if email_taken(db, body.email):
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    user = User(username=username, email=body.email, password_hash=hash_password(body.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # The database's UNIQUE rule caught a duplicate that slipped past the checks above.
        db.rollback()
        raise HTTPException(status_code=409, detail="Username or email already taken")
    db.refresh(user)
    return account_out(user)


@router.post("/login", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # Form fields (username, password) rather than JSON, so the
    # Authorize button in /docs can log in. "username" may also be an email.
    user = find_login_user(db, form.username)

    # Same check and same error whether the username or the password is wrong,
    # so nobody can find out which usernames exist. Google-only accounts have no
    # password, so they fail here the same way.
    password_hash = user.password_hash if user and user.password_hash else DUMMY_HASH
    if not verify_password(form.password, password_hash) or user is None or user.password_hash is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Token(access_token=create_access_token(user.id))


def verified_google_identity(credential: str) -> google.GoogleIdentity:
    try:
        return google.verify_google_credential(credential)
    except google.GoogleNotConfigured:
        raise HTTPException(status_code=503, detail="Google sign-in isn't set up on this server.")
    except google.GoogleUnavailable:
        raise HTTPException(status_code=503, detail="Couldn't reach Google. Please try again.")
    except google.GoogleAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc))


@router.post("/google", response_model=GoogleToken)
def google_login(body: GoogleCredential, db: Session = Depends(get_db)):
    """Sign in (or sign up) with the ID token from the "Sign in with Google" button."""
    identity = verified_google_identity(body.credential)
    user = db.query(User).filter_by(google_sub=identity.sub).first()
    new_account = False
    if user is None:
        # Never attach Google to an existing account just because the email matches: emails
        # aren't verified at sign-up, so someone could have registered with yours first.
        # Existing accounts connect Google from the profile page while logged in.
        try:
            user = create_google_user(db, identity)
        except AccountConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        new_account = True
    return GoogleToken(access_token=create_access_token(user.id), new_account=new_account)


@router.get("/me", response_model=AccountOut)
def me(user: User = Depends(get_current_user)):
    """The logged-in user. Copy this pattern for any endpoint that needs login."""
    return account_out(user)


@router.patch("/me", response_model=AccountOut)
def change_username(body: UsernameChange, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    username = body.username.lower()
    if username != user.username:
        if username_taken(db, username):
            raise HTTPException(status_code=409, detail="Username already taken")
        user.username = username
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=409, detail="Username already taken")
        db.refresh(user)
    return account_out(user)


@router.post("/password", status_code=204)
def change_password(body: PasswordChange, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Change your password, or set a first one on a Google-only account."""
    if user.password_hash is not None:
        # 400, not 401: a wrong current password doesn't mean you're logged out.
        if not body.current_password or not verify_password(body.current_password, user.password_hash):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
    user.password_hash = hash_password(body.new_password)
    db.commit()
    return Response(status_code=204)


@router.post("/google/link", response_model=AccountOut)
def connect_google(body: GoogleCredential, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Connect a Google account to the logged-in account, so either can be used to sign in."""
    identity = verified_google_identity(body.credential)
    try:
        return account_out(link_google(db, user, identity))
    except AccountConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/logout", status_code=204)
def logout(user: User = Depends(get_current_user), token: str = Depends(oauth2_scheme),
           db: Session = Depends(get_db)):
    """Revoke this login token. Other sessions remain signed in."""
    digest = token_digest(token)
    db.add(RevokedToken(token_hash=digest))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # Concurrent logout requests may both pass authentication before revocation.
        if db.get(RevokedToken, digest) is None:
            raise
    return Response(status_code=204)
