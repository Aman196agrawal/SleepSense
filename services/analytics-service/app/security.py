from jose import JWTError, jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import settings

bearer = HTTPBearer()


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(bearer)) -> str:
    payload = decode_token(credentials.credentials)
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")
    return payload["sub"]
