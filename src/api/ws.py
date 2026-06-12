import json
import structlog
from typing import Set, Dict
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime
from ..events import Event, EventType

logger = structlog.get_logger()


class WebSocketManager:
    """Manages WebSocket connections with room-based subscriptions."""

    def __init__(self):
        self._connections: Dict[str, Set[WebSocket]] = {}  # room -> set of websockets
        self._user_rooms: Dict[WebSocket, Set[str]] = {}   # websocket -> set of rooms
        self._total = 0

    async def connect(self, ws: WebSocket, room: str = "all") -> None:
        """Accept a new WebSocket connection and subscribe to a room."""
        await ws.accept()
        self._connections.setdefault(room, set()).add(ws)
        self._user_rooms.setdefault(ws, set()).add(room)
        self._total += 1
        logger.info("WebSocket connected", room=room, total=self._total)

    async def disconnect(self, ws: WebSocket) -> None:
        """Remove a WebSocket from all rooms."""
        rooms = self._user_rooms.pop(ws, set())
        for room in rooms:
            self._connections.get(room, set()).discard(ws)
        self._total = max(0, self._total - 1)
        logger.info("WebSocket disconnected", total=self._total)

    async def subscribe(self, ws: WebSocket, room: str) -> None:
        """Subscribe a connection to an additional room."""
        self._connections.setdefault(room, set()).add(ws)
        self._user_rooms.setdefault(ws, set()).add(room)

    async def unsubscribe(self, ws: WebSocket, room: str) -> None:
        """Unsubscribe a connection from a room."""
        self._connections.get(room, set()).discard(ws)
        self._user_rooms.get(ws, set()).discard(room)

    async def broadcast(self, event: Event, room: str = "all") -> None:
        """Broadcast an event to all connections in a room."""
        payload = event.model_dump_json()
        disconnected = []

        for ws in self._connections.get(room, set()).copy():
            try:
                await ws.send_text(payload)
            except Exception:
                disconnected.append(ws)

        for ws in disconnected:
            await self.disconnect(ws)

    async def broadcast_to_all(self, event: Event) -> None:
        """Broadcast to all connections across all rooms."""
        seen: Set[WebSocket] = set()
        for room_ws in self._connections.values():
            for ws in room_ws:
                if ws not in seen:
                    seen.add(ws)
                    try:
                        await ws.send_text(event.model_dump_json())
                    except Exception:
                        await self.disconnect(ws)

    @property
    def stats(self) -> dict:
        return {
            "total_connections": self._total,
            "rooms": {r: len(ws) for r, ws in self._connections.items() if ws},
        }

    async def handle_websocket(self, ws: WebSocket, room: str = "all") -> None:
        """Full WebSocket lifecycle handler — connect, listen for pings, disconnect."""
        await self.connect(ws, room)
        try:
            while True:
                data = await ws.receive_text()
                try:
                    msg = json.loads(data)
                    action = msg.get("action")
                    if action == "subscribe":
                        await self.subscribe(ws, msg.get("room", "all"))
                        await ws.send_text(json.dumps({"type": "subscribed", "room": msg["room"]}))
                    elif action == "unsubscribe":
                        await self.unsubscribe(ws, msg.get("room", "all"))
                    elif action == "ping":
                        await ws.send_text(json.dumps({"type": "pong", "timestamp": datetime.now().isoformat()}))
                except json.JSONDecodeError:
                    pass
        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.error("WebSocket error", error=str(e))
        finally:
            await self.disconnect(ws)


ws_manager = WebSocketManager()
