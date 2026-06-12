from __future__ import annotations

from fastapi import WebSocket

from app.services.store import now_utc


class EventConnectionManager:
    def __init__(self) -> None:
        self.active_connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self.active_connections.discard(websocket)

    async def broadcast(self, message_type: str, data) -> None:
        disconnected: list[WebSocket] = []
        for websocket in self.active_connections:
            try:
                await websocket.send_json({"type": message_type, "data": data})
            except RuntimeError:
                disconnected.append(websocket)
        for websocket in disconnected:
            self.disconnect(websocket)

    async def heartbeat(self, websocket: WebSocket) -> None:
        await websocket.send_json({
            "type": "heartbeat",
            "data": {"ts": now_utc().isoformat()},
        })


event_manager = EventConnectionManager()
