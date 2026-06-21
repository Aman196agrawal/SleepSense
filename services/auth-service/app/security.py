import uuid
from datetime import datetime, timedelta, timezone
import bcrypt
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import settings

bearer = HTTPBearer()

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(plain: str, hashed: str | None) -> bool:
    # OAuth-only users may have no password hash on file. Treat that as "no
    # password login allowed" rather than crashing.
    if not plain or not hashed:
        return False
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except (ValueError, TypeError):
        return False

def create_access_token(user_id: str, role: str = "user") -> str:
    expire = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": user_id, "exp": expire, "type": "access", "jti": str(uuid.uuid4()), "role": role},
        settings.SECRET_KEY, algorithm=settings.ALGORITHM,
    )

def create_refresh_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return jwt.encode(
        {"sub": user_id, "exp": expire, "type": "refresh", "jti": str(uuid.uuid4())},
        settings.SECRET_KEY, algorithm=settings.ALGORITHM,
    )

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(bearer)) -> str:
    payload = decode_token(credentials.credentials)
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")
    return payload["sub"]


def require_role(*allowed: str):
    """FastAPI dependency that enforces RBAC. Usage: Depends(require_role('admin'))"""
    def _check(credentials: HTTPAuthorizationCredentials = Depends(bearer)) -> str:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user_role = payload.get("role", "user")
        if user_role not in allowed:
            raise HTTPException(status_code=403, detail=f"Requires role: {', '.join(allowed)}")
        return payload["sub"]
    return _check
