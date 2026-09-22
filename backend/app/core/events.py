"""In-process event fan-out to connected browsers (WebSocket).

``manager`` tracks open sockets per user and per job; ``send_job_update`` is
what the scraper task calls to push progress. The WebSocket route itself lives
in ``app.domains.jobs.websocket``.
"""

from __future__ import annotations

from fastapi import WebSocket


class ConnectionManager:
    """Manage WebSocket connections."""

    def __init__(self) -> None:
        # user_id -> set of websockets
        self.active_connections: dict[str, set[WebSocket]] = {}
        # job_uuid -> set of websockets
        self.job_subscriptions: dict[str, set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str) -> None:
        await websocket.accept()
        self.active_connections.setdefault(user_id, set()).add(websocket)

    def disconnect(self, websocket: WebSocket, user_id: str) -> None:
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

        for job_uuid in list(self.job_subscriptions.keys()):
            self.job_subscriptions[job_uuid].discard(websocket)
            if not self.job_subscriptions[job_uuid]:
                del self.job_subscriptions[job_uuid]

    def subscribe_to_job(self, websocket: WebSocket, job_uuid: str) -> None:
        self.job_subscriptions.setdefault(job_uuid, set()).add(websocket)

    def unsubscribe_from_job(self, websocket: WebSocket, job_uuid: str) -> None:
        if job_uuid in self.job_subscriptions:
            self.job_subscriptions[job_uuid].discard(websocket)
            if not self.job_subscriptions[job_uuid]:
                del self.job_subscriptions[job_uuid]

    async def send_to_user(self, user_id: str, message: dict) -> None:
        if user_id not in self.active_connections:
            return
        dead: set[WebSocket] = set()
        for connection in self.active_connections[user_id]:
            try:
                await connection.send_json(message)
            except Exception:
                dead.add(connection)
        for connection in dead:
            self.disconnect(connection, user_id)

    async def send_job_update(self, job_uuid: str, message: dict) -> None:
        if job_uuid not in self.job_subscriptions:
            return
        dead: set[WebSocket] = set()
        for connection in self.job_subscriptions[job_uuid]:
            try:
                await connection.send_json(message)
            except Exception:
                dead.add(connection)
        for connection in dead:
            self.job_subscriptions[job_uuid].discard(connection)

    async def broadcast(self, message: dict) -> None:
        for user_id in list(self.active_connections.keys()):
            await self.send_to_user(user_id, message)


manager = ConnectionManager()


async def send_job_update(job_uuid: str, update_type: str, data: dict) -> None:
    """Push a job update to every subscriber of ``job_uuid``.

    ``update_type`` is one of "progress", "status", "log", "error".
    """
    await manager.send_job_update(
        job_uuid,
        {"type": "job_update", "job_uuid": job_uuid, "update_type": update_type, "data": data},
    )
