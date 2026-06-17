"""
Discord self-bot client.

Uses a user token (discord.py-self) so it can:
  - listen to every channel the account already has access to
  - join new servers via invite links

WARNING: Self-bots violate Discord ToS. Use at your own risk.
"""

import asyncio
import re
from datetime import datetime
from typing import Optional

import discord
from sqlalchemy import select

from app.database import AsyncSessionLocal, CapturedMessage, DiscordLink, Keyword
from app.websocket_manager import manager as ws_manager


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

_INVITE_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:discord\.gg|discord\.com/invite)/([a-zA-Z0-9-]+)"
)


def extract_invite_code(url: str) -> str:
    m = _INVITE_RE.search(url)
    if m:
        return m.group(1)
    # bare code
    return url.strip()


# ──────────────────────────────────────────────
# Client
# ──────────────────────────────────────────────

class DiscordParser(discord.Client):
    def __init__(self) -> None:
        # discord.py-self needs no special intents for user accounts
        super().__init__()
        self._ready = asyncio.Event()
        self.start_time = datetime.utcnow()

    # ── lifecycle ──────────────────────────────

    async def on_ready(self) -> None:
        self._ready.set()
        print(f"[discord] logged in as {self.user} ({self.user.id})")

    async def on_error(self, event: str, *args, **kwargs) -> None:
        import traceback
        print(f"[discord] error in {event}:")
        traceback.print_exc()

    # ── message listener ──────────────────────

    async def on_message(self, message: discord.Message) -> None:
        # ignore own messages
        if message.author == self.user:
            return

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Keyword).where(Keyword.is_active == True)  # noqa: E712
            )
            keywords: list[Keyword] = result.scalars().all()

        matched: list[str] = []
        for kw in keywords:
            needle = kw.keyword if kw.case_sensitive else kw.keyword.lower()
            haystack = message.content if kw.case_sensitive else message.content.lower()
            if needle in haystack:
                matched.append(kw.keyword)

        if not matched:
            return

        guild_name = message.guild.name if message.guild else "DM"
        guild_id = str(message.guild.id) if message.guild else None
        channel_name = getattr(message.channel, "name", "DM")
        channel_id = str(message.channel.id)

        captured = CapturedMessage(
            discord_message_id=str(message.id),
            author_name=str(message.author),
            author_id=str(message.author.id),
            channel_name=channel_name,
            channel_id=channel_id,
            guild_name=guild_name,
            guild_id=guild_id,
            content=message.content,
            matched_keywords=matched,
            captured_at=datetime.utcnow(),
        )
        async with AsyncSessionLocal() as db:
            db.add(captured)
            await db.commit()
            await db.refresh(captured)

        await ws_manager.broadcast(
            {
                "event": "new_message",
                "data": {
                    "id": captured.id,
                    "author_name": captured.author_name,
                    "author_id": captured.author_id,
                    "channel_name": captured.channel_name,
                    "channel_id": captured.channel_id,
                    "guild_name": captured.guild_name,
                    "guild_id": captured.guild_id,
                    "content": captured.content,
                    "matched_keywords": captured.matched_keywords,
                    "is_read": captured.is_read,
                    "captured_at": captured.captured_at.isoformat(),
                },
            }
        )

    # ── invite operations ─────────────────────

    async def check_invite(self, invite_url: str) -> dict:
        """Return status dict without joining."""
        code = extract_invite_code(invite_url)
        try:
            invite = await self.fetch_invite(code)
            return {
                "status": "valid",
                "guild_id": str(invite.guild.id) if invite.guild else None,
                "guild_name": invite.guild.name if invite.guild else None,
            }
        except discord.NotFound:
            return {"status": "invalid", "error": "Invite not found or expired"}
        except discord.Forbidden as exc:
            return {"status": "error", "error": str(exc)}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    async def join_via_invite(self, invite_url: str, link_id: int) -> dict:
        """Join a server and update the DB record."""
        code = extract_invite_code(invite_url)
        try:
            invite = await self.fetch_invite(code)
            # Already in this server?
            if invite.guild and any(g.id == invite.guild.id for g in self.guilds):
                result = {
                    "status": "active",
                    "guild_id": str(invite.guild.id),
                    "guild_name": invite.guild.name,
                }
            else:
                await invite.accept()
                result = {
                    "status": "active",
                    "guild_id": str(invite.guild.id) if invite.guild else None,
                    "guild_name": invite.guild.name if invite.guild else None,
                }
        except discord.NotFound:
            result = {"status": "invalid", "error": "Invite not found or expired"}
        except discord.Forbidden as exc:
            msg = str(exc).lower()
            if "verification" in msg or "captcha" in msg or "phone" in msg:
                result = {"status": "approval_required", "error": str(exc)}
            else:
                result = {"status": "error", "error": str(exc)}
        except Exception as exc:
            result = {"status": "error", "error": str(exc)}

        async with AsyncSessionLocal() as db:
            link = await db.get(DiscordLink, link_id)
            if link:
                link.status = result["status"]
                link.guild_id = result.get("guild_id")
                link.guild_name = result.get("guild_name")
                link.error_message = result.get("error")
                link.last_checked = datetime.utcnow()
                await db.commit()

        return result

    async def refresh_link(self, link_id: int) -> dict:
        async with AsyncSessionLocal() as db:
            link = await db.get(DiscordLink, link_id)
            if not link:
                return {"status": "error", "error": "Link not found"}
            url = link.invite_url

        return await self.join_via_invite(url, link_id)

    # ── status ────────────────────────────────

    def status_info(self) -> dict:
        if not self._ready.is_set():
            return {"connected": False, "user": None, "guilds": [], "uptime_seconds": 0}
        return {
            "connected": True,
            "user": str(self.user),
            "user_id": str(self.user.id) if self.user else None,
            "guilds": [
                {"id": str(g.id), "name": g.name, "member_count": g.member_count}
                for g in self.guilds
            ],
            "uptime_seconds": int((datetime.utcnow() - self.start_time).total_seconds()),
        }


# Module-level singleton — populated by main.py on startup
discord_client: Optional[DiscordParser] = None
