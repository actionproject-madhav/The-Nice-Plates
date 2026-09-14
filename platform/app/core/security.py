"""Token issuance and verification.

Google proves who the user is once; after that we carry our own short JWT so
every request doesn't cost a round trip to Google.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt

from app.config import settings

ALGORITHM = settings.jwt_algorithm


class TokenError(Exception):
    pass


def issue_access_token(user_id: str, email: str, role: str) -> tuple[str, int]:
    """Returns (token, expires_in_seconds)."""
    ttl = timedelta(minutes=settings.access_token_ttl_minutes)
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + ttl).timestamp()),
        "iss": "nice-plates",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM), int(ttl.total_seconds())


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM], issuer="nice-plates")
    except JWTError as exc:
        raise TokenError(str(exc)) from exc


def verify_google_id_token(id_token_str: str) -> dict[str, Any]:
    """Verify a Google ID token and return its claims.

    Imported lazily so the module loads in environments without google-auth
    (the ML worker's test runs, for instance).
    """
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token as google_id_token

    if not settings.google_configured:
        raise TokenError("GOOGLE_CLIENT_ID is not set on the API.")

    try:
        claims = google_id_token.verify_oauth2_token(
            id_token_str, google_requests.Request(), settings.google_client_id
        )
    except ValueError as exc:
        raise TokenError(f"Google rejected this token: {exc}") from exc

    if claims.get("iss") not in {"accounts.google.com", "https://accounts.google.com"}:
        raise TokenError("Unexpected token issuer.")
    if not claims.get("email_verified", False):
        raise TokenError("This Google account has no verified email address.")
    return claims
