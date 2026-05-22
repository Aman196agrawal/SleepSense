import uuid
import time
import secrets
import json as _json
import logging
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, RefreshToken, SocialAccount, PasswordResetToken, EmailVerificationToken
from app.schemas import (
    RegisterRequest, LoginRequest, RefreshRequest, TokenResponse,
    SocialLoginRequest, ForgotPasswordRequest, ResetPasswordRequest,
    VerifyEmailRequest,
)
from app.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token,
    decode_token,
)
from app.config import settings
from app.redis_client import get_redis

router = APIRouter()
_logger = logging.getLogger(__name__)


def _send_email(to: str, subject: str, html: str) -> None:
    """Send a transactional email via SendGrid, falling back to logging when
    SENDGRID_API_KEY is not configured (dev / test environments)."""
    if not settings.SENDGRID_API_KEY:
        _logger.info("[EMAIL SKIPPED — no SENDGRID_API_KEY] To: %s | Subject: %s", to, subject)
        return
    import json as _json_email
    payload = _json_email.dumps({
        "personalizations": [{"to": [{"email": to}]}],
        "from": {"email": settings.SENDGRID_FROM_EMAIL},
        "subject": subject,
        "content": [{"type": "text/html", "value": html}],
    }).encode()
    req = urllib.request.Request(
        "https://api.sendgrid.com/v3/mail/send",
        data=payload,
        headers={
            "Authorization": f"Bearer {settings.SENDGRID_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status >= 300:
                _logger.warning("SendGrid returned %s for %s", resp.status, to)
    except Exception:
        _logger.warning("SendGrid send failed for %s", to, exc_info=True)


# ── Refresh token helpers ──────────────────────────────────────────────────────

def _store_in_db(token: str, user_id: str, db: Session) -> None:
    rt = RefreshToken(
        id=str(uuid.uuid4()),
        user_id=user_id,
        token=token,
        expires_at=datetime.now(timezone.utc).replace(tzinfo=None)
                   + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(rt)
    db.commit()


def _store_refresh_token(token: str, user_id: str, db: Session) -> None:
    r = get_redis()
    if r:
        try:
            r.setex(f"rt:{token}", settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400, user_id)
            return
        except Exception:
            _logger.warning("Redis store failed — falling back to DB", exc_info=True)
    _store_in_db(token, user_id, db)


def _consume_from_db(token: str, db: Session) -> str:
    rt = db.query(RefreshToken).filter(
        RefreshToken.token == token,
        RefreshToken.is_revoked == False,
    ).first()
    if not rt or rt.expires_at < datetime.now(timezone.utc).replace(tzinfo=None):
        raise HTTPException(status_code=401, detail="Refresh token expired or revoked")
    rt.is_revoked = True
    db.commit()
    return rt.user_id


def _consume_refresh_token(token: str, db: Session) -> str:
    """Validate + rotate: returns user_id or raises 401."""
    r = get_redis()
    if r:
        try:
            user_id = r.get(f"rt:{token}")
            if user_id:
                r.delete(f"rt:{token}")
                return user_id
            # Redis is up but the token isn't there — could be expired/revoked,
            # or could have been written before Redis was wired up. Fall back
            # to DB to be safe rather than 401-ing valid tokens.
        except Exception:
            _logger.warning("Redis consume failed — falling back to DB", exc_info=True)
    return _consume_from_db(token, db)


def _revoke_refresh_token(token: str, db: Session) -> None:
    r = get_redis()
    if r:
        try:
            r.delete(f"rt:{token}")
        except Exception:
            _logger.warning("Redis revoke failed — falling through to DB", exc_info=True)
    rt = db.query(RefreshToken).filter(RefreshToken.token == token).first()
    if rt and not rt.is_revoked:
        rt.is_revoked = True
        db.commit()


# ── Rate limiting (sliding window, 10 req / 15 min per IP) ───────────────────

_rl_store: dict[str, list[float]] = {}  # ip → list of request timestamps (in-memory fallback)


def _check_rate_limit(ip: str, action: str = "login") -> None:
    r = get_redis()
    if r:
        try:
            key = f"ratelimit:{action}:{ip}"
            count = r.incr(key)
            if count == 1:
                r.expire(key, 900)  # 15 minutes
            if count > 10:
                raise HTTPException(status_code=429, detail="Too many login attempts. Try again later.")
            return
        except HTTPException:
            raise
        except Exception:
            _logger.warning("Redis rate-limit check failed — falling back to in-memory", exc_info=True)

    now = time.time()
    window = 900.0
    store_key = f"{action}:{ip}"
    timestamps = [t for t in _rl_store.get(store_key, []) if now - t < window]
    timestamps.append(now)
    _rl_store[store_key] = timestamps
    if len(timestamps) > 10:
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again later.")


# ── Google OAuth2 token verification ──────────────────────────────────────────

def _verify_google_token(id_token: str) -> dict:
    """Validate a Google ID token via Google's public tokeninfo endpoint."""
    url = f"https://oauth2.googleapis.com/tokeninfo?id_token={id_token}"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            info = _json.loads(resp.read())
    except urllib.error.HTTPError:
        raise HTTPException(status_code=401, detail="Invalid Google token")
    except Exception:
        raise HTTPException(status_code=503, detail="Could not verify Google token")

    if settings.GOOGLE_CLIENT_ID and info.get("aud") != settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=401, detail="Token audience mismatch")

    return info


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/register", response_model=TokenResponse, status_code=201)
def register(request: Request, body: RegisterRequest, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "unknown"
    _check_rate_limit(ip, "register")

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

    access  = create_access_token(user.id, getattr(user, 'role', 'user'))
    refresh = create_refresh_token(user.id)
    _store_refresh_token(refresh, user.id, db)

    # Generate a dedicated one-time verification token (not the bearer access token)
    verify_token = secrets.token_urlsafe(32)
    evt = EmailVerificationToken(
        user_id=user.id,
        token=verify_token,
        expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=24),
    )
    db.add(evt)
    db.commit()

    verify_url = f"{settings.FRONTEND_URL}/verify-email?token={verify_token}"
    _send_email(
        to=user.email,
        subject="SleepSense — Verify your email",
        html=f"<p>Welcome to SleepSense! Verify your email to get started:</p><a href='{verify_url}'>{verify_url}</a>",
    )

    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/verify-email")
def verify_email(body: VerifyEmailRequest, db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    evt = db.query(EmailVerificationToken).filter(
        EmailVerificationToken.token == body.token,
        EmailVerificationToken.is_used == False,
    ).first()
    if not evt or evt.expires_at < now:
        raise HTTPException(status_code=400, detail="Invalid or expired verification link")
    user = db.query(User).filter(User.id == evt.user_id).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid verification link")
    user.is_verified = True
    evt.is_used = True
    db.commit()
    return {"message": "Email verified successfully"}


@router.post("/login", response_model=TokenResponse)
def login(request: Request, body: LoginRequest, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "unknown"
    _check_rate_limit(ip)

    user = db.query(User).filter(User.email == body.email).first()
    if not user or not user.password_hash or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access  = create_access_token(user.id, getattr(user, 'role', 'user'))
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


@router.post("/social/google", response_model=TokenResponse)
def social_google(body: SocialLoginRequest, db: Session = Depends(get_db)):
    info = _verify_google_token(body.id_token)

    if not info.get("email_verified") in (True, "true"):
        raise HTTPException(status_code=401, detail="Google email not verified")

    google_uid   = info.get("sub", "")
    email        = info.get("email", "")
    display_name = info.get("name", "")

    if not google_uid or not email:
        raise HTTPException(status_code=401, detail="Incomplete Google token payload")

    social = db.query(SocialAccount).filter(
        SocialAccount.provider == "google",
        SocialAccount.provider_uid == google_uid,
    ).first()

    if social:
        user = db.query(User).filter(User.id == social.user_id).first()
        if not user:
            raise HTTPException(status_code=401, detail="Associated account no longer exists")
    else:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            user = User(
                id=str(uuid.uuid4()),
                email=email,
                password_hash=None,
                display_name=display_name,
            )
            db.add(user)
            db.flush()

        social = SocialAccount(
            user_id=user.id,
            provider="google",
            provider_uid=google_uid,
        )
        db.add(social)
        db.commit()

    access  = create_access_token(user.id, getattr(user, 'role', 'user'))
    refresh = create_refresh_token(user.id)
    _store_refresh_token(refresh, user.id, db)

    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/social/apple", response_model=TokenResponse)
def social_apple(body: SocialLoginRequest, db: Session = Depends(get_db)):
    """Apple Sign-In.

    Decodes the Apple identity token payload to extract `sub` (Apple user ID)
    and `email`. In production, validate the RS256 JWT signature against Apple's
    public JWK set from https://appleid.apple.com/auth/keys. The sample build
    trusts the decoded payload (acceptable for dev; add jose/cryptography-based
    verification before App Store submission).
    """
    import base64 as _b64
    try:
        parts = body.id_token.split('.')
        if len(parts) != 3:
            raise ValueError("bad format")
        padded = parts[1] + '=' * (4 - len(parts[1]) % 4)
        claims = _json.loads(_b64.urlsafe_b64decode(padded))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid Apple identity token")

    apple_uid = claims.get("sub", "")
    email = claims.get("email", "")
    if not apple_uid:
        raise HTTPException(status_code=401, detail="Incomplete Apple token payload")

    social = db.query(SocialAccount).filter(
        SocialAccount.provider == "apple",
        SocialAccount.provider_uid == apple_uid,
    ).first()

    if social:
        user = db.query(User).filter(User.id == social.user_id).first()
        if not user:
            raise HTTPException(status_code=401, detail="Associated account no longer exists")
    else:
        user = db.query(User).filter(User.email == email).first() if email else None
        if not user:
            user = User(
                id=str(uuid.uuid4()),
                email=email or f"apple_{apple_uid}@privaterelay.appleid.com",
                password_hash=None,
                display_name=claims.get("name", "Apple User"),
            )
            db.add(user)
            db.flush()

        social = SocialAccount(
            user_id=user.id,
            provider="apple",
            provider_uid=apple_uid,
        )
        db.add(social)
        db.commit()

    access  = create_access_token(user.id, getattr(user, 'role', 'user'))
    refresh = create_refresh_token(user.id)
    _store_refresh_token(refresh, user.id, db)

    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/forgot-password")
def forgot_password(body: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if user:
        db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.is_used == False,
        ).update({"is_used": True})

        token = secrets.token_urlsafe(32)
        prt = PasswordResetToken(
            user_id=user.id,
            token=token,
            expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1),
        )
        db.add(prt)
        db.commit()

        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token}"
        _logger.info("Password reset link for %s: %s", user.email, reset_url)
        _send_email(
            to=user.email,
            subject="SleepSense — Reset your password",
            html=f"<p>Click to reset your password (valid 1 hour):</p><a href='{reset_url}'>{reset_url}</a>",
        )

    return {"message": "If that email is registered, a reset link has been sent."}


@router.post("/reset-password")
def reset_password(body: ResetPasswordRequest, db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    prt = db.query(PasswordResetToken).filter(
        PasswordResetToken.token == body.token,
        PasswordResetToken.is_used == False,
    ).first()

    if not prt or prt.expires_at < now:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    user = db.query(User).filter(User.id == prt.user_id).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid reset token")

    user.password_hash = hash_password(body.new_password)
    prt.is_used = True

    db.query(RefreshToken).filter(
        RefreshToken.user_id == user.id,
        RefreshToken.is_revoked == False,
    ).update({"is_revoked": True})

    db.commit()
    return {"message": "Password updated successfully"}
