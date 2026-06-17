import aiohttp
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import OkResponse, TokenBody, TokenSetOut, TokenStatusOut
from app.database import AppConfig, get_db

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


async def _validate_token(token: str) -> dict:
    """Hit Discord's API to confirm the token is a valid user token."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://discord.com/api/v10/users/@me",
                headers={"Authorization": token},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("bot"):
                        return {
                            "valid": False,
                            "error": "Bot tokens are not supported. Please use your personal user token (from the browser Authorization header).",
                        }
                    username = data.get("username", "")
                    discriminator = data.get("discriminator", "0")
                    display = f"{username}#{discriminator}" if discriminator != "0" else username
                    return {"valid": True, "user": display, "user_id": str(data["id"])}
                elif resp.status == 401:
                    return {"valid": False, "error": "Invalid token — Discord rejected it."}
                else:
                    return {"valid": False, "error": f"Discord API returned {resp.status}."}
    except aiohttp.ClientError as exc:
        return {"valid": False, "error": f"Could not reach Discord API: {exc}"}


@router.post("/token", response_model=TokenSetOut)
async def set_token(body: TokenBody, db: AsyncSession = Depends(get_db)):
    """Validate a Discord user token and save it; starts/restarts the Discord client."""
    result = await _validate_token(body.token)
    if not result["valid"]:
        raise HTTPException(status_code=401, detail=result["error"])

    # Upsert into app_config
    row = await db.get(AppConfig, "discord_token")
    if row:
        row.value = body.token
    else:
        db.add(AppConfig(key="discord_token", value=body.token))
    await db.commit()

    # Start (or restart) the Discord client with the new token
    from app.discord_client import start_discord
    await start_discord(body.token)

    return TokenSetOut(user=result["user"], user_id=result["user_id"])


@router.get("/token/status", response_model=TokenStatusOut)
async def token_status(db: AsyncSession = Depends(get_db)):
    """Check whether a token is saved (regardless of connection state)."""
    row = await db.get(AppConfig, "discord_token")
    return TokenStatusOut(has_token=row is not None)


@router.delete("/token", response_model=OkResponse)
async def clear_token(db: AsyncSession = Depends(get_db)):
    """Remove the saved token and disconnect the Discord client."""
    import app.discord_client as dc_module

    if dc_module.discord_client:
        try:
            await dc_module.discord_client.close()
        except Exception:
            pass
        dc_module.discord_client = None

    row = await db.get(AppConfig, "discord_token")
    if row:
        await db.delete(row)
        await db.commit()

    return OkResponse(detail="Token cleared — Discord client disconnected.")
