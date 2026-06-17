import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from app.database import AppConfig, AsyncSessionLocal, init_db
from app.websocket_manager import manager as ws_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()

    # Load token from DB; fall back to env for backward-compat
    from app.config import settings
    from app.discord_client import start_discord

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(AppConfig).where(AppConfig.key == "discord_token"))
        row = result.scalar_one_or_none()
        token = row.value if row else None

    if not token and settings.discord_token:
        token = settings.discord_token
        async with AsyncSessionLocal() as db:
            db.add(AppConfig(key="discord_token", value=token))
            await db.commit()

    if token:
        await start_discord(token)
    else:
        print("[warn] No Discord token configured. Set it via the web UI.")

    yield


app = FastAPI(
    title="Discord Parser",
    description="Monitor Discord channels for keywords",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# ── REST routes ───────────────────────────────────────────────────────────────

from app.api.routes import auth, keywords, links, messages, status  # noqa: E402

app.include_router(auth.router)
app.include_router(links.router)
app.include_router(keywords.router)
app.include_router(messages.router)
app.include_router(status.router)

# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)

# ── Static frontend ───────────────────────────────────────────────────────────

import pathlib  # noqa: E402

STATIC_DIR = pathlib.Path(__file__).parent / "static"

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
async def serve_frontend():
    return FileResponse(str(STATIC_DIR / "index.html"))
