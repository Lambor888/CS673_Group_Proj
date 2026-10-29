"""Account notifications, independent of lobby membership (single worker)."""
import asyncio

from fastapi import WebSocket, WebSocketDisconnect


class AccountNotifications:
    def __init__(self):
        self.connections: dict[int, set[WebSocket]] = {}

    def add(self, user_id: int, ws: WebSocket):
        self.connections.setdefault(user_id, set()).add(ws)

    def remove(self, user_id: int, ws: WebSocket):
        connections = self.connections.get(user_id)
        if connections is not None:
            connections.discard(ws)
            if not connections:
                self.connections.pop(user_id, None)

    async def send(self, user_id: int, message: dict):
        for ws in tuple(self.connections.get(user_id, ())):
            try:
                await asyncio.wait_for(ws.send_json(message), timeout=2)
            except (OSError, RuntimeError, asyncio.TimeoutError, WebSocketDisconnect):
                self.remove(user_id, ws)


notifications = AccountNotifications()
