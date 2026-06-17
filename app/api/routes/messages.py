from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import MessageListOut, MessageOut, OkResponse
from app.database import CapturedMessage, get_db

router = APIRouter(prefix="/api/v1/messages", tags=["messages"])


@router.get("", response_model=MessageListOut)
async def list_messages(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    keyword: Optional[str] = Query(None),
    unread_only: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    q = select(CapturedMessage)

    if unread_only:
        q = q.where(CapturedMessage.is_read == False)  # noqa: E712

    if keyword:
        q = q.where(CapturedMessage.content.ilike(f"%{keyword}%"))

    total_result = await db.execute(select(func.count()).select_from(q.subquery()))
    total = total_result.scalar_one()

    q = q.order_by(CapturedMessage.captured_at.desc()).offset(skip).limit(limit)
    result = await db.execute(q)
    items = result.scalars().all()

    return MessageListOut(total=total, items=items)


@router.get("/{msg_id}", response_model=MessageOut)
async def get_message(msg_id: int, db: AsyncSession = Depends(get_db)):
    msg = await db.get(CapturedMessage, msg_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    return msg


@router.post("/{msg_id}/read", response_model=MessageOut)
async def mark_read(msg_id: int, db: AsyncSession = Depends(get_db)):
    msg = await db.get(CapturedMessage, msg_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    msg.is_read = True
    await db.commit()
    await db.refresh(msg)
    return msg


@router.post("/read-all", response_model=OkResponse)
async def mark_all_read(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CapturedMessage).where(CapturedMessage.is_read == False)  # noqa: E712
    )
    msgs = result.scalars().all()
    for m in msgs:
        m.is_read = True
    await db.commit()
    return OkResponse(detail=f"Marked {len(msgs)} messages as read")


@router.delete("/{msg_id}", response_model=OkResponse)
async def delete_message(msg_id: int, db: AsyncSession = Depends(get_db)):
    msg = await db.get(CapturedMessage, msg_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    await db.delete(msg)
    await db.commit()
    return OkResponse(detail="Message deleted")


@router.delete("", response_model=OkResponse)
async def delete_all_messages(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(CapturedMessage))
    msgs = result.scalars().all()
    for m in msgs:
        await db.delete(m)
    await db.commit()
    return OkResponse(detail=f"Deleted {len(msgs)} messages")
