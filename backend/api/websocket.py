"""WebSocket connection manager for real-time client communication."""
import asyncio
import logging
from datetime import datetime, timezone

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections with thread-safe broadcast."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        async with self._lock:
            self.active_connections.append(websocket)
        logger.info("WebSocket connected (%d total)", self.client_count)

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection."""
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
        logger.info("WebSocket disconnected (%d remaining)", self.client_count)

    async def broadcast(self, message: dict) -> None:
        """Send a message to all connected clients, removing dead connections."""
        dead = []
        async with self._lock:
            connections = list(self.active_connections)

        for ws in connections:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)

        if dead:
            async with self._lock:
                for ws in dead:
                    if ws in self.active_connections:
                        self.active_connections.remove(ws)
            logger.debug("Removed %d dead connections", len(dead))

    async def send_to(self, websocket: WebSocket, message: dict) -> None:
        """Send a message to a specific client."""
        try:
            await websocket.send_json(message)
        except Exception:
            await self.disconnect(websocket)

    @property
    def client_count(self) -> int:
        return len(self.active_connections)


# Singleton instance
ws_manager = ConnectionManager()


def make_envelope(msg_type: str, data: dict) -> dict:
    """Create a standard WebSocket message envelope.

    Returns:
        {"type": msg_type, "timestamp": ISO-8601, "data": data}
    """
    return {
        "type": msg_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }
