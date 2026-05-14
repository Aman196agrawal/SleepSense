import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException
from app.security import decode_token

router = APIRouter()
_logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self._active: dict[str, list[WebSocket]] = {}

    async def connect(self, user_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self._active.setdefault(user_id, []).append(ws)
        _logger.debug("WebSocket connected: user=%s total=%d", user_id, len(self._active[user_id]))

    def disconnect(self, user_id: str, ws: WebSocket) -> None:
        conns = self._active.get(user_id, [])
        if ws in conns:
            conns.remove(ws)
        if not conns:
            self._active.pop(user_id, None)

    async def send_to_user(self, user_id: str, event: dict) -> None:
        for ws in list(self._active.get(user_id, [])):
            try:
                await ws.send_json(event)
            except Exception:
                pass


manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket, token: str = Query(...)):
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            await ws.close(code=1008)
            return
        user_id = payload["sub"]
    except HTTPException:
        await ws.close(code=1008)
        return

    await manager.connect(user_id, ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(user_id, ws)
    except Exception as exc:
        _logger.debug("WebSocket error for user=%s: %s", user_id, exc)
        manager.disconnect(user_id, ws)
