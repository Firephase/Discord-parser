from fastapi import APIRouter

from app.api.schemas import StatusOut
from app.websocket_manager import manager as ws_manager

router = APIRouter(prefix="/api/v1/status", tags=["status"])


@router.get("", response_model=StatusOut)
async def get_status():
    from app.discord_client import discord_client

    if discord_client:
        info = discord_client.status_info()
    else:
        info = {
            "connected": False,
            "user": None,
            "user_id": None,
            "guilds": [],
            "uptime_seconds": 0,
            "invite_url": None,
        }

    return StatusOut(
        **info,
        websocket_clients=ws_manager.client_count,
    )
