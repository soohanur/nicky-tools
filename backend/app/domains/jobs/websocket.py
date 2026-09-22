"""WebSocket route for real-time job updates.

Connect with the JWT as a query parameter: ``ws://host/api/v1/ws?token=<jwt>``.

Client -> server:
    {"action": "subscribe", "job_uuid": "<uuid>"}
    {"action": "unsubscribe", "job_uuid": "<uuid>"}
    {"action": "ping"}

Server -> client:
    {"type": "connected", ...}
    {"type": "subscribed" | "unsubscribed", "job_uuid": "<uuid>"}
    {"type": "job_update", "job_uuid": "<uuid>", "update_type": "...", "data": {...}}
    {"type": "pong"}
"""

from __future__ import annotations

import contextlib
import json

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.auth.jwt import decode_access_token
from app.core.events import manager

router = APIRouter(prefix="/ws", tags=["WebSocket"])


@router.websocket("")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(..., description="JWT access token"),
) -> None:
    user_id = decode_access_token(token)
    if not user_id:
        await websocket.close(code=1008, reason="Invalid token")
        return

    await manager.connect(websocket, user_id)

    try:
        await websocket.send_json(
            {"type": "connected", "user_id": user_id, "message": "WebSocket connected successfully"}
        )

        while True:
            message = json.loads(await websocket.receive_text())
            action = message.get("action")

            if action == "subscribe":
                job_uuid = message.get("job_uuid")
                if job_uuid:
                    manager.subscribe_to_job(websocket, job_uuid)
                    await websocket.send_json({"type": "subscribed", "job_uuid": job_uuid})

            elif action == "unsubscribe":
                job_uuid = message.get("job_uuid")
                if job_uuid:
                    manager.unsubscribe_from_job(websocket, job_uuid)
                    await websocket.send_json({"type": "unsubscribed", "job_uuid": job_uuid})

            elif action == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)

    except Exception as exc:  # noqa: BLE001 - any failure closes the socket
        manager.disconnect(websocket, user_id)
        with contextlib.suppress(Exception):
            await websocket.close(code=1011, reason=str(exc))
