"""Google sign-in.

Flow: the browser gets an ID token from Google Identity Services, POSTs it
here, we verify it against Google's keys, upsert the user, and hand back our
own JWT. Google's token is never stored.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status

from app.core.security import TokenError, issue_access_token, verify_google_id_token
from app.deps import Claims, Db
from app.schemas import AuthResponse, GoogleLoginRequest, UserPublic
from nplates_data.collections import Collections
from nplates_data.models import Role, User, utcnow

log = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


def _public(doc: dict) -> UserPublic:
    return UserPublic(
        id=str(doc["_id"]),
        email=doc["email"],
        name=doc.get("name", ""),
        picture=doc.get("picture"),
        role=doc.get("role", Role.STUDENT.value),
        instrument=doc.get("instrument"),
    )


@router.post("/google", response_model=AuthResponse)
async def google_login(body: GoogleLoginRequest, db: Db) -> AuthResponse:
    try:
        claims = verify_google_id_token(body.credential)
    except TokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc

    users = db[Collections.USERS]
    now = utcnow()
    google_sub = claims["sub"]

    # Upsert on the Google subject: the one identifier Google guarantees is
    # stable. Emails get reassigned; subs don't.
    await users.update_one(
        {"google_sub": google_sub},
        {
            "$set": {
                "email": claims.get("email", ""),
                "name": claims.get("name") or claims.get("email", "").split("@")[0],
                "picture": claims.get("picture"),
                "last_login_at": now,
                "updated_at": now,
            },
            "$setOnInsert": {
                "google_sub": google_sub,
                "role": Role.STUDENT.value,
                "instrument": None,
                "created_at": now,
            },
        },
        upsert=True,
    )

    doc = await users.find_one({"google_sub": google_sub})
    if doc is None:  # pragma: no cover - upsert just ran
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Could not create your account.")

    token, expires_in = issue_access_token(
        str(doc["_id"]), doc["email"], doc.get("role", Role.STUDENT.value)
    )
    return AuthResponse(access_token=token, expires_in=expires_in, user=_public(doc))


@router.get("/me", response_model=UserPublic)
async def me(claims: Claims, db: Db) -> UserPublic:
    from bson import ObjectId

    doc = await db[Collections.USERS].find_one({"_id": ObjectId(claims["sub"])})
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That account no longer exists.")
    return _public(doc)


@router.patch("/me", response_model=UserPublic)
async def update_me(claims: Claims, db: Db, instrument: str | None = None) -> UserPublic:
    from bson import ObjectId

    updates = {"updated_at": utcnow()}
    if instrument is not None:
        updates["instrument"] = instrument
    await db[Collections.USERS].update_one({"_id": ObjectId(claims["sub"])}, {"$set": updates})
    doc = await db[Collections.USERS].find_one({"_id": ObjectId(claims["sub"])})
    return _public(doc)


# Dev-only shortcut so the frontend and the practice loop can be built before
# the Google OAuth consent screen is approved. Refuses to run in production.
@router.post("/dev-login", response_model=AuthResponse, include_in_schema=False)
async def dev_login(db: Db, email: str = "dev@nice-plates.local") -> AuthResponse:
    from app.config import settings

    if settings.is_production:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.")

    users = db[Collections.USERS]
    user = User(google_sub=f"dev|{email}", email=email, name="Dev User", instrument="piano")

    # Mongo rejects an update that touches the same path in $set and
    # $setOnInsert, so the insert-only document must not carry last_login_at.
    on_insert = user.to_mongo()
    on_insert.pop("last_login_at", None)
    await users.update_one(
        {"google_sub": user.google_sub},
        {"$set": {"last_login_at": utcnow()}, "$setOnInsert": on_insert},
        upsert=True,
    )
    doc = await users.find_one({"google_sub": user.google_sub})
    token, expires_in = issue_access_token(str(doc["_id"]), doc["email"], doc["role"])
    return AuthResponse(access_token=token, expires_in=expires_in, user=_public(doc))
