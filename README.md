# Discord Parser

A self-hosted web application that monitors Discord channels for user-defined keywords and surfaces matching messages in a real-time dashboard.

## Features

- **Keyword monitoring** — define keywords (case-sensitive or not); every incoming Discord message is checked against them
- **Server joining** — paste any Discord invite link; the client joins the server automatically and marks it active / error / needs approval
- **Real-time feed** — new matches appear instantly in the browser via WebSocket
- **REST API** — all functionality exposed as JSON endpoints so a Telegram bot (or any other client) can integrate later
- **Persistent storage** — SQLite database stored on the host via a Docker volume

---

## ⚠️ Discord ToS Warning

This application uses a **user token** (self-bot) so it can listen to every channel you already have access to and join servers via invite links. Self-bots violate [Discord's Terms of Service](https://discord.com/terms). Use at your own risk and only with accounts you own.

---

## Quick Start

### 1. Get your Discord token

1. Open Discord in a browser and press **F12** → Network tab
2. Filter by `api` and refresh the page (or send any message)
3. Click any request to `discord.com/api/…`
4. In the **Request Headers**, find `Authorization` — that value is your token

### 2. Configure

```bash
cp .env.example .env
# Edit .env and set DISCORD_TOKEN=your_token
```

### 3. Run with Docker

```bash
docker compose up -d
```

The app is available at **http://your-vps-ip:8000**

### 4. Run locally (without Docker)

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # set DISCORD_TOKEN
mkdir -p data
uvicorn app.main:app --reload
```

---

## REST API Reference

Base URL: `http://your-host:8000/api/v1`

Interactive docs: `GET /api/docs` (Swagger) or `/api/redoc`

All responses are JSON. Errors return `{"detail": "…"}`.

---

### Status

#### `GET /api/v1/status`

Returns Discord client connection state.

**Response**
```json
{
  "connected": true,
  "user": "username#0000",
  "user_id": "123456789",
  "guilds": [
    { "id": "111", "name": "My Server", "member_count": 42 }
  ],
  "uptime_seconds": 3600,
  "websocket_clients": 1
}
```

---

### Keywords

#### `GET /api/v1/keywords`

List all keywords.

**Response** — array of keyword objects
```json
[
  {
    "id": 1,
    "keyword": "tutor",
    "is_active": true,
    "case_sensitive": false,
    "created_at": "2024-01-01T12:00:00"
  }
]
```

---

#### `POST /api/v1/keywords`

Add a new keyword.

**Body**
```json
{
  "keyword": "tutor",
  "case_sensitive": false
}
```

**Response** `201` — keyword object

**Errors**
- `409` — keyword already exists

---

#### `PUT /api/v1/keywords/{id}`

Update a keyword (toggle active / case-sensitive).

**Body** (all fields optional)
```json
{
  "is_active": false,
  "case_sensitive": true
}
```

**Response** — updated keyword object

---

#### `DELETE /api/v1/keywords/{id}`

Remove a keyword.

**Response**
```json
{ "ok": true, "detail": "Keyword removed" }
```

---

### Discord Links

#### `GET /api/v1/links`

List all saved invite links.

**Response** — array of link objects
```json
[
  {
    "id": 1,
    "invite_url": "https://discord.gg/abcdef",
    "invite_code": "abcdef",
    "guild_id": "999888777",
    "guild_name": "My Server",
    "status": "active",
    "error_message": null,
    "added_at": "2024-01-01T12:00:00",
    "last_checked": "2024-01-01T12:00:05"
  }
]
```

**Status values:**

| Value | Meaning |
|-------|---------|
| `pending` | Saved, join attempt in progress |
| `active` | Successfully joined / already a member |
| `invalid` | Invite not found or expired |
| `approval_required` | Server requires phone verification or manual approval |
| `error` | Unexpected error (see `error_message`) |

---

#### `POST /api/v1/links`

Add a new invite link and attempt to join the server.

**Body**
```json
{
  "invite_url": "https://discord.gg/abcdef"
}
```

**Response** `201` — link object (status starts as `pending`, updated asynchronously)

**Errors**
- `409` — link already saved
- `503` — Discord client not connected

---

#### `DELETE /api/v1/links/{id}`

Remove a saved link.

**Response**
```json
{ "ok": true, "detail": "Link removed" }
```

---

#### `POST /api/v1/links/{id}/refresh`

Re-check a link's status and attempt to join again.

**Response** — updated link object

---

### Captured Messages

#### `GET /api/v1/messages`

List captured messages (newest first).

**Query parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `skip` | int | `0` | Pagination offset |
| `limit` | int | `50` | Max results (1–200) |
| `keyword` | string | — | Filter by content substring |
| `unread_only` | bool | `false` | Return only unread messages |

**Response**
```json
{
  "total": 42,
  "items": [
    {
      "id": 1,
      "discord_message_id": "1234567890",
      "author_name": "User#1234",
      "author_id": "111222333",
      "channel_name": "general",
      "channel_id": "444555666",
      "guild_name": "My Server",
      "guild_id": "999888777",
      "content": "I'm looking for a tutor in Python",
      "matched_keywords": ["tutor"],
      "is_read": false,
      "captured_at": "2024-01-01T12:00:00"
    }
  ]
}
```

---

#### `GET /api/v1/messages/{id}`

Get a single message by ID.

---

#### `POST /api/v1/messages/{id}/read`

Mark a message as read.

**Response** — updated message object

---

#### `POST /api/v1/messages/read-all`

Mark all messages as read.

**Response**
```json
{ "ok": true, "detail": "Marked 15 messages as read" }
```

---

#### `DELETE /api/v1/messages/{id}`

Delete a single message.

---

#### `DELETE /api/v1/messages`

Delete **all** captured messages.

---

### WebSocket

#### `WS /ws`

Connect to receive real-time events.

**Events sent by server:**

```json
{
  "event": "new_message",
  "data": {
    "id": 1,
    "author_name": "User#1234",
    "author_id": "111222333",
    "channel_name": "general",
    "channel_id": "444555666",
    "guild_name": "My Server",
    "guild_id": "999888777",
    "content": "I'm looking for a tutor in Python",
    "matched_keywords": ["tutor"],
    "is_read": false,
    "captured_at": "2024-01-01T12:00:00"
  }
}
```

Send any text (e.g. `"ping"`) to keep the connection alive.

---

## Architecture

```
┌─────────────────────────────────────┐
│            Docker Container         │
│                                     │
│  ┌──────────────────────────────┐   │
│  │         FastAPI (uvicorn)    │   │
│  │  REST API  /api/v1/*         │   │
│  │  WebSocket /ws               │   │
│  │  Static UI /                 │   │
│  └──────────┬───────────────────┘   │
│             │  same asyncio loop    │
│  ┌──────────▼───────────────────┐   │
│  │     discord.py-self client   │   │
│  │  on_message → keyword check  │   │
│  │  join via invite links       │   │
│  └──────────┬───────────────────┘   │
│             │                       │
│  ┌──────────▼───────────────────┐   │
│  │     SQLite (data/db.sqlite)  │   │
│  └──────────────────────────────┘   │
│                                     │
└──────────────┬──────────────────────┘
               │ volume mount
          ./data/discord_parser.db
```

## Future: Telegram Bot Integration

The REST API is intentionally designed to be consumed by external clients. A Telegram bot can:

1. Call `POST /api/v1/keywords` to add keywords from Telegram commands
2. Poll `GET /api/v1/messages?unread_only=true` (or use WebSocket) to forward matches to Telegram
3. Call `POST /api/v1/messages/read-all` after forwarding

The web app and Telegram bot can run as separate services — they both talk to the same REST API.
