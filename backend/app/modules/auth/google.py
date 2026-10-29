"""Checks the ID token the "Sign in with Google" button hands the browser.

The browser gets a token signed by Google; we verify the signature with Google's public keys and
check it was issued for our client id. No client secret is involved, so there's nothing secret
to configure beyond the client id.
"""

from dataclasses import dataclass

import jwt

from app.config import settings

GOOGLE_CERTS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = ["accounts.google.com", "https://accounts.google.com"]


class GoogleNotConfigured(Exception):
    pass


class GoogleUnavailable(Exception):
    pass


class GoogleAuthError(Exception):
    pass


@dataclass(frozen=True)
class GoogleIdentity:
    sub: str  # Google's permanent account id; emails can change, this can't
    email: str  # lowercase, verified by Google
    name: str | None


_jwks_client: jwt.PyJWKClient | None = None


def _signing_key(token: str):
    """Google's public key for this token (cached; Google rotates them every few days)."""
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = jwt.PyJWKClient(GOOGLE_CERTS_URL, cache_keys=True, lifespan=3600, timeout=5)
    return _jwks_client.get_signing_key_from_jwt(token).key


def verify_google_credential(credential: str) -> GoogleIdentity:
    client_id = settings.google_client_id.strip()
    if not client_id:
        raise GoogleNotConfigured()
    try:
        claims = jwt.decode(
            credential,
            _signing_key(credential),
            algorithms=["RS256"],
            audience=client_id,  # issued for this app, not some other site
            issuer=GOOGLE_ISSUERS,
            leeway=60,  # small clock differences between us and Google
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )
    except jwt.PyJWKClientConnectionError:
        raise GoogleUnavailable() from None
    except jwt.PyJWTError:
        raise GoogleAuthError("Google sign-in failed. Please try again.") from None

    email = claims.get("email")
    if not isinstance(email, str) or claims.get("email_verified") is not True:
        raise GoogleAuthError("Your Google account needs a verified email address.")
    name = claims.get("name")
    return GoogleIdentity(
        sub=str(claims["sub"]),
        email=email.strip().lower(),
        name=name if isinstance(name, str) else None,
    )
