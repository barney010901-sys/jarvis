"""The `/ws` endpoint: the Android app's real-time channel.

Protocol (JSON both ways):
- Client -> server: {"type": "user.message", "session_id": "...", "project": "...", "text": "..."}
- Server -> client: every `Event` published on the bus while this connection
  is open, as `event.model_dump_json_safe()`.

Auth: the token is passed as a query parameter (`?token=...`) since browser/
RN WebSocket clients can't set an Authorization header on the handshake.
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.config import get_settings
from app.deps import get_event_bus, get_orchestrator

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws")
async def ws_endpoint(websocket: WebSocket, token: str = Query(default="")) -> None:
    settings = get_settings()
    if token != settings.jarvis_api_token:
        await websocket.close(code=4401)
        return

    await websocket.accept()
    event_bus = get_event_bus()
    queue, unsubscribe = event_bus.subscribe_queue()

    async def forward_events() -> None:
        while True:
            event = await queue.get()
            await websocket.send_json(event.model_dump_json_safe())

    forward_task = asyncio.create_task(forward_events())
    try:
        while True:
            message = await websocket.receive_json()
            if message.get("type") == "user.message":
                await get_orchestrator().handle_message(
                    session_id=message.get("session_id", "default"),
                    project=message.get("project", "default"),
                    text=message.get("text", ""),
                )
            else:
                logger.warning("Unrecognized message type on /ws: %s", message.get("type"))
    except WebSocketDisconnect:
        pass
    finally:
        forward_task.cancel()
        unsubscribe()
