"""Repertoire: pieces and their practice sections."""

from __future__ import annotations

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, HTTPException, Response, status

from app.deps import Db, UserId
from app.schemas import ChunkRequest, PieceCreate, PieceUpdate, SectionCreate
from nplates_data.collections import Collections
from nplates_data.models import Piece, Section, utcnow

router = APIRouter(prefix="/pieces", tags=["pieces"])


def oid(value: str, what: str = "id") -> ObjectId:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"That {what} isn't valid.") from exc


def serialize(doc: dict) -> dict:
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id"))
    return doc


async def owned_piece(db, piece_id: str, user_id: str) -> dict:
    doc = await db[Collections.PIECES].find_one({"_id": oid(piece_id), "owner_id": user_id})
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "We couldn't find that piece.")
    return doc


@router.get("")
async def list_pieces(db: Db, user_id: UserId, limit: int = 50) -> list[dict]:
    cursor = (
        db[Collections.PIECES]
        .find({"owner_id": user_id})
        .sort("updated_at", -1)
        .limit(min(limit, 200))
    )
    return [serialize(d) async for d in cursor]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_piece(body: PieceCreate, db: Db, user_id: UserId) -> dict:
    piece = Piece(owner_id=user_id, **body.model_dump())
    result = await db[Collections.PIECES].insert_one(piece.to_mongo())
    doc = await db[Collections.PIECES].find_one({"_id": result.inserted_id})
    return serialize(doc)


@router.get("/{piece_id}")
async def get_piece(piece_id: str, db: Db, user_id: UserId) -> dict:
    doc = await owned_piece(db, piece_id, user_id)
    sections = (
        db[Collections.SECTIONS].find({"piece_id": piece_id}).sort("index", 1)
    )
    out = serialize(doc)
    out["sections"] = [serialize(s) async for s in sections]
    return out


@router.patch("/{piece_id}")
async def update_piece(piece_id: str, body: PieceUpdate, db: Db, user_id: UserId) -> dict:
    await owned_piece(db, piece_id, user_id)
    updates = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    updates["updated_at"] = utcnow()
    await db[Collections.PIECES].update_one({"_id": oid(piece_id)}, {"$set": updates})
    return serialize(await db[Collections.PIECES].find_one({"_id": oid(piece_id)}))


# response_model=None: a `-> None` annotation makes FastAPI infer NoneType,
# which is truthy, and 204 forbids a response body.
@router.delete(
    "/{piece_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
async def delete_piece(piece_id: str, db: Db, user_id: UserId) -> None:
    await owned_piece(db, piece_id, user_id)
    await db[Collections.PIECES].delete_one({"_id": oid(piece_id)})
    await db[Collections.SECTIONS].delete_many({"piece_id": piece_id})


# ── Sections ───────────────────────────────────────────────────────────────


@router.post("/{piece_id}/sections", status_code=status.HTTP_201_CREATED)
async def add_section(piece_id: str, body: SectionCreate, db: Db, user_id: UserId) -> dict:
    await owned_piece(db, piece_id, user_id)
    if body.end_bar < body.start_bar:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A section can't end before it starts.")

    count = await db[Collections.SECTIONS].count_documents({"piece_id": piece_id})
    section = Section(piece_id=piece_id, owner_id=user_id, index=count, **body.model_dump())
    result = await db[Collections.SECTIONS].insert_one(section.to_mongo())
    return serialize(await db[Collections.SECTIONS].find_one({"_id": result.inserted_id}))


@router.post("/{piece_id}/chunk")
async def chunk_piece(piece_id: str, body: ChunkRequest, db: Db, user_id: UserId) -> list[dict]:
    """Split a piece into fixed-width practice sections.

    Deliberately dumb for v0: even runs of bars. The proposal's real chunking
    algorithm (phrase boundaries, cadences, difficulty weighting) replaces the
    body of this function without touching its signature or any caller.
    """
    await owned_piece(db, piece_id, user_id)

    if body.replace_existing:
        await db[Collections.SECTIONS].delete_many({"piece_id": piece_id})

    sections: list[Section] = []
    index = 0
    for start in range(1, body.total_bars + 1, body.bars_per_section):
        end = min(start + body.bars_per_section - 1, body.total_bars)
        sections.append(
            Section(
                piece_id=piece_id,
                owner_id=user_id,
                index=index,
                label=f"Bars {start}–{end}" if end > start else f"Bar {start}",
                start_bar=start,
                end_bar=end,
            )
        )
        index += 1

    if sections:
        await db[Collections.SECTIONS].insert_many([s.to_mongo() for s in sections])

    cursor = db[Collections.SECTIONS].find({"piece_id": piece_id}).sort("index", 1)
    return [serialize(s) async for s in cursor]
