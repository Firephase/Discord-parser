from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import KeywordCreate, KeywordOut, KeywordUpdate, OkResponse
from app.database import Keyword, get_db

router = APIRouter(prefix="/api/v1/keywords", tags=["keywords"])


@router.get("", response_model=list[KeywordOut])
async def list_keywords(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Keyword).order_by(Keyword.created_at.desc()))
    return result.scalars().all()


@router.post("", response_model=KeywordOut, status_code=201)
async def add_keyword(body: KeywordCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(
        select(Keyword).where(Keyword.keyword == body.keyword)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Keyword already exists")

    kw = Keyword(keyword=body.keyword, case_sensitive=body.case_sensitive)
    db.add(kw)
    await db.commit()
    await db.refresh(kw)
    return kw


@router.put("/{kw_id}", response_model=KeywordOut)
async def update_keyword(
    kw_id: int, body: KeywordUpdate, db: AsyncSession = Depends(get_db)
):
    kw = await db.get(Keyword, kw_id)
    if not kw:
        raise HTTPException(status_code=404, detail="Keyword not found")

    if body.is_active is not None:
        kw.is_active = body.is_active
    if body.case_sensitive is not None:
        kw.case_sensitive = body.case_sensitive

    await db.commit()
    await db.refresh(kw)
    return kw


@router.delete("/{kw_id}", response_model=OkResponse)
async def delete_keyword(kw_id: int, db: AsyncSession = Depends(get_db)):
    kw = await db.get(Keyword, kw_id)
    if not kw:
        raise HTTPException(status_code=404, detail="Keyword not found")
    await db.delete(kw)
    await db.commit()
    return OkResponse(detail="Keyword removed")
