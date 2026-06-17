import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_db
from app.websocket_manager import manager as ws_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()

    if not settings.discord_token:
        print("[warn] DISCORD_TOKEN is not set — Discord client will not start")
    else:
        import app.discord_client as dc_module

        client = dc_module.DiscordParser()
        dc_module.discord_client = client

        async def _run():
            try:
                await client.start(settings.discord_token)
            except Exception as exc:
                print(f"[discord] client stopped: {exc}")

        task = asyncio.create_task(_run())

    yield

    # Shutdown: cancel background discord task if running
    for t in asyncio.all_tasks():
        if t.get_name().startswith("Task-") and not t.done():
            pass  # let discord.py-self handle its own cleanup


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

from app.api.routes import keywords, links, messages, status  # noqa: E402

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
            # Keep connection alive; client sends pings
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
