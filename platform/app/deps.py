"""Request dependencies."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core import db as db_module
from app.core.security import TokenError, decode_access_token


def get_db() -> AsyncIOMotorDatabase:
    return db_module.get_db()


Db = Annotated[AsyncIOMotorDatabase, Depends(get_db)]


async def current_user_claims(
    authorization: Annotated[str | None, Header()] = None,
) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign in to continue.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization.split(" ", 1)[1].strip()
    try:
        return decode_access_token(token)
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Your session has expired. ({exc})",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


Claims = Annotated[dict, Depends(current_user_claims)]


async def current_user_id(claims: Claims) -> str:
    return claims["sub"]


UserId = Annotated[str, Depends(current_user_id)]
