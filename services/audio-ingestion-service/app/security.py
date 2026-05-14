from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from app.config import settings

_bearer = HTTPBearer()


def get_current_user_id(creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> str:
    try:
        payload = jwt.decode(creds.credentials, settings.SECRET_KEY, algorithms=["HS256"])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user_id
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def create_upload_token(session_id: str) -> str:
    """Session-scoped JWT valid for UPLOAD_TOKEN_TTL_HOURS to authorise chunk uploads."""
    payload = {
        "sub": session_id,
        "type": "upload",
        "exp": datetime.now(timezone.utc) + timedelta(hours=settings.UPLOAD_TOKEN_TTL_HOURS),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
