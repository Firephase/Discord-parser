import asyncio
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import LinkCreate, LinkOut, OkResponse
from app.database import DiscordLink, get_db

router = APIRouter(prefix="/api/v1/links", tags=["links"])


def _get_client():
    from app.discord_client import discord_client
    return discord_client


@router.get("", response_model=list[LinkOut])
async def list_links(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DiscordLink).order_by(DiscordLink.added_at.desc()))
    return result.scalars().all()


@router.post("", response_model=LinkOut, status_code=201)
async def add_link(body: LinkCreate, db: AsyncSession = Depends(get_db)):
    from app.discord_client import extract_invite_code

    code = extract_invite_code(body.invite_url)

    # Prevent duplicates
    existing = await db.execute(
        select(DiscordLink).where(DiscordLink.invite_code == code)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="This invite link is already saved")

    link = DiscordLink(
        invite_url=body.invite_url,
        invite_code=code,
        status="pending",
        added_at=datetime.utcnow(),
    )
    db.add(link)
    await db.commit()
    await db.refresh(link)

    # Fire-and-forget: join in background so the HTTP response returns immediately
    client = _get_client()
    if client and client._ready.is_set():
        asyncio.create_task(client.join_via_invite(body.invite_url, link.id))
    else:
        link.status = "error"
        link.error_message = "Discord client not connected"
        link.last_checked = datetime.utcnow()
        await db.commit()
        await db.refresh(link)

    return link


@router.delete("/{link_id}", response_model=OkResponse)
async def delete_link(link_id: int, db: AsyncSession = Depends(get_db)):
    link = await db.get(DiscordLink, link_id)
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
    await db.delete(link)
    await db.commit()
    return OkResponse(detail="Link removed")


@router.post("/{link_id}/refresh", response_model=LinkOut)
async def refresh_link(link_id: int, db: AsyncSession = Depends(get_db)):
    link = await db.get(DiscordLink, link_id)
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")

    client = _get_client()
    if not client or not client._ready.is_set():
        raise HTTPException(status_code=503, detail="Discord client not connected")

    await client.refresh_link(link_id)
    await db.refresh(link)
    return link
