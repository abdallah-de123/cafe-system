"""WebSocket hub with scoped delivery.

Two kinds of connections:
- staff: connected with a valid JWT (?token=). They receive every event.
- customer: connected with their order tokens (?orders=tok1,tok2). They only receive
  `order_updated` for their own orders plus public events (menu/settings changes).
"""
import logging
from typing import Any, Dict, List, Set

from fastapi import WebSocket

logger = logging.getLogger("restos")

PUBLIC_EVENTS = {"menu_updated", "settings_updated"}


class Connection:
    """One socket plus what it is allowed to see."""

    def __init__(self, ws: WebSocket, staff: bool, order_tokens: Set[str]):
        self.ws = ws
        self.staff = staff
        self.order_tokens = order_tokens


class Manager:
    """Keeps the live connections and routes events to those allowed to see them."""

    def __init__(self):
        self.conns: List[Connection] = []

    async def connect(self, ws: WebSocket, staff: bool, order_tokens: Set[str]) -> Connection:
        await ws.accept()
        c = Connection(ws, staff, order_tokens)
        self.conns.append(c)
        return c

    def disconnect(self, c: Connection):
        if c in self.conns:
            self.conns.remove(c)

    def _allowed(self, c: Connection, event: str, data: Any) -> bool:
        """Decide whether this connection may receive the event."""
        if c.staff:
            return True
        if event in PUBLIC_EVENTS:
            return True
        if event == "order_updated" and isinstance(data, dict):
            return data.get("public_token") in c.order_tokens
        return False

    async def broadcast(self, event: str, data: Any):
        """Send an event to every connection that is allowed to see it."""
        for c in list(self.conns):
            if not self._allowed(c, event, data):
                continue
            payload = data
            # Customers never receive staff-only fields.
            if not c.staff and isinstance(data, dict):
                payload = {k: v for k, v in data.items() if k not in ("accepted_by",)}
            try:
                await c.ws.send_json({"event": event, "data": payload})
            except Exception:
                self.disconnect(c)


manager = Manager()
