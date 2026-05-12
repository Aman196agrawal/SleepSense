import uuid
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, RefreshToken
from app.schemas import RegisterRequest, LoginRequest, RefreshRequest, TokenResponse
from app.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token,
    decode_token
)
from app.config import settings
from app.redis_client import get_redis

router = APIRouter()

# ── Refresh token helpers ──────────────────────────────────────────────────────
# Redis (if configured): key = "rt:{token}" → user_id, TTL = REFRESH_TOKEN_EXPIRE_DAYS
# Fallback: RefreshToken table in PostgreSQL/SQLite

def _store_refresh_token(token: str, user_id: str, db: Session) -> None:
    r = get_redis()
    if r:
        r.setex(
            f"rt:{token}",
            settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
            user_id,
        )
    else:
        rt = RefreshToken(
            id=str(uuid.uuid4()),
            user_id=user_id,
            token=token,
            expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
        db.add(rt)
        db.commit()


def _consume_refresh_token(token: str, db: Session) -> str:
    """Validate + rotate: returns user_id or raises 401."""
    r = get_redis()
    if r:
        user_id = r.get(f"rt:{token}")
        if not user_id:
            raise HTTPException(status_code=401, detail="Refresh token expired or revoked")
        r.delete(f"rt:{token}")
        return user_id
    else:
        rt = db.query(RefreshToken).filter(
            RefreshToken.token == token,
            RefreshToken.is_revoked == False,
        ).first()
        if not rt or rt.expires_at < datetime.now(timezone.utc).replace(tzinfo=None):
            raise HTTPException(status_code=401, detail="Refresh token expired or revoked")
        rt.is_revoked = True
        db.commit()
        return rt.user_id


def _revoke_refresh_token(token: str, db: Session) -> None:
    r = get_redis()
    if r:
        r.delete(f"rt:{token}")
    else:
        rt = db.query(RefreshToken).filter(RefreshToken.token == token).first()
        if rt:
            rt.is_revoked = True
            db.commit()


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/register", response_model=TokenResponse, status_code=201)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        id=str(uuid.uuid4()),
        email=body.email,
        password_hash=hash_password(body.password),
        display_name=body.display_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    access  = create_access_token(user.id)
    refresh = create_refresh_token(user.id)
    _store_refresh_token(refresh, user.id, db)

    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access  = create_access_token(user.id)
    refresh = create_refresh_token(user.id)
    _store_refresh_token(refresh, user.id, db)

    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh")
def refresh_token(body: RefreshRequest, db: Session = Depends(get_db)):
    payload = decode_token(body.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")

    user_id = _consume_refresh_token(body.refresh_token, db)

    new_access  = create_access_token(user_id)
    new_refresh = create_refresh_token(user_id)
    _store_refresh_token(new_refresh, user_id, db)

    return {"access_token": new_access, "refresh_token": new_refresh, "token_type": "bearer"}


@router.post("/logout")
def logout(body: RefreshRequest, db: Session = Depends(get_db)):
    _revoke_refresh_token(body.refresh_token, db)
    return {"message": "Logged out"}
