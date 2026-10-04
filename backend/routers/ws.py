"""WebSocket endpoint. Staff pass ?token=<jwt>; customers pass ?orders=tok1,tok2."""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException

from core.security import user_from_token
from core.ws import manager

router = APIRouter()


@router.websocket("/api/ws")
async def ws_endpoint(ws: WebSocket, token: str = "", orders: str = ""):
    """Authenticate the socket, then keep it open until the client leaves."""
    staff = False
    if token:
        try:
            await user_from_token(token)
            staff = True
        except HTTPException:
            await ws.close(code=4401)
            return
    order_tokens = {t for t in orders.split(",") if t}
    conn = await manager.connect(ws, staff, order_tokens)
    try:
        while True:
            # Clients may send "ping"; we ignore the content and just keep the socket alive.
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(conn)
    except Exception:
        manager.disconnect(conn)
