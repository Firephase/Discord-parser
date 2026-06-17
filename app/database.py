from datetime import datetime
from typing import AsyncGenerator

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import JSON

from app.config import settings

engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class DiscordLink(Base):
    __tablename__ = "discord_links"

    id = Column(Integer, primary_key=True, index=True)
    invite_url = Column(String, nullable=False)
    invite_code = Column(String)
    guild_id = Column(String)
    guild_name = Column(String)
    # pending | active | error | approval_required | invalid
    status = Column(String, default="pending")
    error_message = Column(Text)
    added_at = Column(DateTime, default=datetime.utcnow)
    last_checked = Column(DateTime)


class Keyword(Base):
    __tablename__ = "keywords"

    id = Column(Integer, primary_key=True, index=True)
    keyword = Column(String, nullable=False, unique=True)
    is_active = Column(Boolean, default=True)
    case_sensitive = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class CapturedMessage(Base):
    __tablename__ = "captured_messages"

    id = Column(Integer, primary_key=True, index=True)
    discord_message_id = Column(String)
    author_name = Column(String, nullable=False)
    author_id = Column(String, nullable=False)
    channel_name = Column(String, nullable=False)
    channel_id = Column(String, nullable=False)
    guild_name = Column(String)
    guild_id = Column(String)
    content = Column(Text, nullable=False)
    matched_keywords = Column(JSON)
    is_read = Column(Boolean, default=False)
    captured_at = Column(DateTime, default=datetime.utcnow)


class AppConfig(Base):
    """Key-value store for runtime configuration (e.g. discord token)."""
    __tablename__ = "app_config"

    key = Column(String, primary_key=True)
    value = Column(Text, nullable=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
