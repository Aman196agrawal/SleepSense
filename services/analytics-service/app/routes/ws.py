import asyncio
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from app.security import decode_token

router = APIRouter()
_logger = logging.getLogger(__name__)

_AUTH_TIMEOUT_SECONDS = 10


class ConnectionManager:
    def __init__(self):
        self._active: dict[str, list[WebSocket]] = {}

    async def connect(self, user_id: str, ws: WebSocket) -> None:
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
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()

    # Post-accept auth: client must send {"token": "<access_token>"} within 10 seconds.
    # This keeps bearer tokens out of server logs and browser history.
    try:
        raw = await asyncio.wait_for(ws.receive_text(), timeout=_AUTH_TIMEOUT_SECONDS)
        msg = json.loads(raw)
        token = msg.get("token", "")
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise ValueError("wrong token type")
        user_id = payload["sub"]
    except (asyncio.TimeoutError, Exception) as exc:
        _logger.debug("WS auth failed: %s", exc)
        await ws.close(code=1008)
        return

    await manager.connect(user_id, ws)

    async def heartbeat():
        try:
            while True:
                await asyncio.sleep(30)
                await ws.send_json({"event": "ping"})
        except Exception:
            pass

    hb_task = asyncio.create_task(heartbeat())
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        _logger.debug("WebSocket error for user=%s: %s", user_id, exc)
    finally:
        hb_task.cancel()
        manager.disconnect(user_id, ws)
