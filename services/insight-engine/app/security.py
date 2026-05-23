from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from jose import JWTError, jwt

from app.config import settings

_bearer = HTTPBearer(auto_error=False)


def get_current_user_id(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    if not creds:
        raise HTTPException(status_code=401, detail="Missing auth token")
    try:
        payload = jwt.decode(creds.credentials, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Wrong token type")
        return user_id
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


def require_role(*allowed: str):
    """FastAPI dependency enforcing RBAC (SEC-003). Usage: Depends(require_role('admin'))"""
    def _check(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> str:
        if not creds:
            raise HTTPException(status_code=401, detail="Missing auth token")
        try:
            payload = jwt.decode(creds.credentials, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        except JWTError:
            raise HTTPException(status_code=401, detail="Invalid token")
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Wrong token type")
        user_role = payload.get("role", "user")
        if user_role not in allowed:
            raise HTTPException(status_code=403, detail=f"Requires role: {', '.join(allowed)}")
        return payload["sub"]
    return _check
