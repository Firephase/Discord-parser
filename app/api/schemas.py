from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


# ── Discord Links ──────────────────────────────────────────

class LinkCreate(BaseModel):
    invite_url: str

class LinkOut(BaseModel):
    id: int
    invite_url: str
    invite_code: Optional[str]
    guild_id: Optional[str]
    guild_name: Optional[str]
    status: str
    error_message: Optional[str]
    added_at: datetime
    last_checked: Optional[datetime]

    model_config = {"from_attributes": True}


# ── Keywords ───────────────────────────────────────────────

class KeywordCreate(BaseModel):
    keyword: str
    case_sensitive: bool = False

class KeywordUpdate(BaseModel):
    is_active: Optional[bool] = None
    case_sensitive: Optional[bool] = None

class KeywordOut(BaseModel):
    id: int
    keyword: str
    is_active: bool
    case_sensitive: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Captured Messages ──────────────────────────────────────

class MessageOut(BaseModel):
    id: int
    discord_message_id: Optional[str]
    author_name: str
    author_id: str
    channel_name: str
    channel_id: str
    guild_name: Optional[str]
    guild_id: Optional[str]
    content: str
    matched_keywords: Optional[list[str]]
    is_read: bool
    captured_at: datetime

    model_config = {"from_attributes": True}


class MessageListOut(BaseModel):
    total: int
    items: list[MessageOut]


# ── Status ─────────────────────────────────────────────────

class StatusOut(BaseModel):
    connected: bool
    user: Optional[str]
    user_id: Optional[str]
    guilds: list[dict[str, Any]]
    uptime_seconds: int
    websocket_clients: int


# ── Auth ───────────────────────────────────────────────────

class TokenBody(BaseModel):
    token: str

class TokenSetOut(BaseModel):
    ok: bool = True
    user: str
    user_id: str

class TokenStatusOut(BaseModel):
    has_token: bool


# ── Generic ────────────────────────────────────────────────

class OkResponse(BaseModel):
    ok: bool = True
    detail: str = "success"
