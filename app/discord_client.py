import asyncio
import re
from datetime import datetime
from typing import Optional

import discord
from sqlalchemy import select

from app.database import AsyncSessionLocal, CapturedMessage, Keyword
from app.websocket_manager import manager as ws_manager


_INVITE_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:discord\.gg|discord\.com/invite)/([a-zA-Z0-9-]+)"
)


def extract_invite_code(url: str) -> str:
    m = _INVITE_RE.search(url)
    if m:
        return m.group(1)
    return url.strip()


class DiscordParser(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True  # Privileged — enable in Dev Portal → Bot → Privileged Gateway Intents
        intents.guilds = True
        intents.guild_messages = True
        super().__init__(intents=intents)
        self._ready = asyncio.Event()
        self.start_time = datetime.utcnow()

    async def on_ready(self) -> None:
        self._ready.set()
        print(f"[discord] logged in as {self.user} ({self.user.id})")
        print(f"[discord] in {len(self.guilds)} server(s)")

    async def on_error(self, event: str, *args, **kwargs) -> None:
        import traceback
        print(f"[discord] error in {event}:")
        traceback.print_exc()

    async def on_message(self, message: discord.Message) -> None:
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

    def invite_url(self) -> Optional[str]:
        if not self.user:
            return None
        perms = discord.Permissions(view_channel=True, read_message_history=True)
        return discord.utils.oauth_url(str(self.user.id), permissions=perms, scopes=("bot",))

    def status_info(self) -> dict:
        if not self._ready.is_set():
            return {
                "connected": False,
                "user": None,
                "user_id": None,
                "guilds": [],
                "uptime_seconds": 0,
                "invite_url": None,
            }
        return {
            "connected": True,
            "user": str(self.user),
            "user_id": str(self.user.id) if self.user else None,
            "guilds": [
                {"id": str(g.id), "name": g.name, "member_count": g.member_count}
                for g in self.guilds
            ],
            "uptime_seconds": int((datetime.utcnow() - self.start_time).total_seconds()),
            "invite_url": self.invite_url(),
        }


# ── Runtime management ────────────────────────────────────────────────────────

discord_client: Optional[DiscordParser] = None
_discord_task: Optional[asyncio.Task] = None


async def start_discord(token: str) -> None:
    global discord_client, _discord_task

    if discord_client:
        try:
            await discord_client.close()
        except Exception:
            pass

    if _discord_task and not _discord_task.done():
        _discord_task.cancel()
        try:
            await asyncio.wait_for(asyncio.shield(_discord_task), timeout=5.0)
        except (asyncio.CancelledError, asyncio.TimeoutError, Exception):
            pass

    client = DiscordParser()
    discord_client = client

    async def _run() -> None:
        try:
            await client.start(token)
        except Exception as exc:
            print(f"[discord] client stopped: {exc}")

    _discord_task = asyncio.create_task(_run())
