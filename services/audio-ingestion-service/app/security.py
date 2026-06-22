from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from app.config import settings

_bearer = HTTPBearer()


def _decode(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def get_current_user_id(creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> str:
    payload = _decode(creds.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user_id


def require_role(*allowed: str):
    def _check(creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> str:
        payload = _decode(creds.credentials)
        role = payload.get("role", "user")
        if role not in allowed:
            raise HTTPException(status_code=403, detail=f"Requires role: {', '.join(allowed)}")
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user_id
    return _check


def create_upload_token(session_id: str, user_id: str) -> str:
    """Session-scoped JWT valid for UPLOAD_TOKEN_TTL_HOURS to authorise chunk uploads.
    Bound to (session_id, user_id) so it can only be used by its owner."""
    payload = {
        "sub": session_id,
        "uid": user_id,
        "type": "upload",
        "exp": datetime.now(timezone.utc) + timedelta(hours=settings.UPLOAD_TOKEN_TTL_HOURS),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def verify_upload_token(token: str, session_id: str) -> str:
    """Validate a session-scoped upload token and return the bound user_id.

    Raises 401 if the token is invalid/expired, not an upload token, or not scoped
    to this session. Lets the ingestion service safely create its record for a
    session that was created elsewhere (analytics-service) without trusting any
    authenticated caller to claim an arbitrary session_id.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired upload token")
    if payload.get("type") != "upload" or payload.get("sub") != session_id:
        raise HTTPException(status_code=401, detail="Upload token is not valid for this session")
    uid = payload.get("uid")
    if not uid:
        raise HTTPException(status_code=401, detail="Upload token missing user binding")
    return uid
