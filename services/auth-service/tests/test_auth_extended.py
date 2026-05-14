"""
Tests for:
  POST /auth/social/google      — Google OAuth2 social login
  POST /auth/forgot-password    — Initiate password reset
  POST /auth/reset-password     — Complete password reset
  POST /auth/login (rate limit) — 429 after 10 requests in 15 min
"""
import logging
from unittest.mock import patch
from fastapi import HTTPException


_GOOGLE_INFO = {
    "sub": "google-uid-12345",
    "email": "googleuser@gmail.com",
    "name": "Google User",
    "email_verified": "true",
}


def _social_post(client, info=None):
    with patch("app.routes.auth._verify_google_token") as mock:
        mock.return_value = info or _GOOGLE_INFO
        return client.post("/auth/social/google", json={"id_token": "fake-token"})


# ── /auth/social/google ────────────────────────────────────────────────────────

class TestSocialGoogle:
    def test_returns_200(self, client):
        assert _social_post(client).status_code == 200

    def test_returns_token_payload(self, client):
        body = _social_post(client).json()
        assert "access_token" in body
        assert "refresh_token" in body
        assert body["token_type"] == "bearer"
        assert body["expires_in"] > 0

    def test_creates_user_accessible_via_get_me(self, client):
        tokens = _social_post(client).json()
        profile = client.get("/users/me", headers={
            "Authorization": f"Bearer {tokens['access_token']}"
        }).json()
        assert profile["email"] == "googleuser@gmail.com"

    def test_links_existing_email_account(self, client):
        client.post("/auth/register", json={
            "email": "googleuser@gmail.com",
            "password": "Test1234!",
            "display_name": "Email User",
        })
        resp = _social_post(client)
        assert resp.status_code == 200

    def test_second_login_returns_same_user_id(self, client):
        tokens1 = _social_post(client).json()
        tokens2 = _social_post(client).json()
        user1 = client.get("/users/me", headers={"Authorization": f"Bearer {tokens1['access_token']}"}).json()
        user2 = client.get("/users/me", headers={"Authorization": f"Bearer {tokens2['access_token']}"}).json()
        assert user1["id"] == user2["id"]

    def test_google_error_returns_401(self, client):
        with patch("app.routes.auth._verify_google_token") as mock:
            mock.side_effect = HTTPException(status_code=401, detail="Invalid Google token")
            resp = client.post("/auth/social/google", json={"id_token": "bad-token"})
        assert resp.status_code == 401

    def test_social_only_user_cannot_login_with_password(self, client):
        _social_post(client)
        resp = client.post("/auth/login", json={
            "email": "googleuser@gmail.com",
            "password": "anything",
        })
        assert resp.status_code == 401

    def test_missing_id_token_returns_422(self, client):
        resp = client.post("/auth/social/google", json={})
        assert resp.status_code == 422

    def test_unverified_email_returns_401(self, client):
        with patch("app.routes.auth._verify_google_token") as mock:
            mock.return_value = {**_GOOGLE_INFO, "email_verified": "false"}
            resp = client.post("/auth/social/google", json={"id_token": "fake-token"})
        assert resp.status_code == 401
        assert "verified" in resp.json()["detail"].lower()

    def test_unverified_email_bool_false_returns_401(self, client):
        with patch("app.routes.auth._verify_google_token") as mock:
            mock.return_value = {**_GOOGLE_INFO, "email_verified": False}
            resp = client.post("/auth/social/google", json={"id_token": "fake-token"})
        assert resp.status_code == 401

    def test_orphaned_social_account_returns_401(self, client, db_session):
        from app.models import SocialAccount
        orphan = SocialAccount(
            user_id="non-existent-user-id",
            provider="google",
            provider_uid="orphan-uid-999",
        )
        db_session.add(orphan)
        db_session.commit()

        with patch("app.routes.auth._verify_google_token") as mock:
            mock.return_value = {**_GOOGLE_INFO, "sub": "orphan-uid-999"}
            resp = client.post("/auth/social/google", json={"id_token": "fake-token"})
        assert resp.status_code == 401
        assert "no longer exists" in resp.json()["detail"]


# ── /auth/forgot-password ──────────────────────────────────────────────────────

class TestForgotPassword:
    def test_registered_email_returns_200(self, client, registered_user):
        resp = client.post("/auth/forgot-password", json={"email": "aman@sleepsense.app"})
        assert resp.status_code == 200

    def test_unknown_email_also_returns_200(self, client):
        resp = client.post("/auth/forgot-password", json={"email": "ghost@sleepsense.app"})
        assert resp.status_code == 200

    def test_same_message_for_known_and_unknown_email(self, client, registered_user):
        r_known   = client.post("/auth/forgot-password", json={"email": "aman@sleepsense.app"})
        r_unknown = client.post("/auth/forgot-password", json={"email": "ghost@sleepsense.app"})
        assert r_known.json()["message"] == r_unknown.json()["message"]

    def test_invalid_email_format_returns_422(self, client):
        resp = client.post("/auth/forgot-password", json={"email": "not-an-email"})
        assert resp.status_code == 422

    def test_logs_reset_link_for_registered_user(self, client, registered_user, caplog):
        with caplog.at_level(logging.INFO, logger="app.routes.auth"):
            client.post("/auth/forgot-password", json={"email": "aman@sleepsense.app"})
        assert any("reset-password" in r.message for r in caplog.records)

    def test_does_not_log_anything_for_unknown_email(self, client, caplog):
        with caplog.at_level(logging.INFO, logger="app.routes.auth"):
            client.post("/auth/forgot-password", json={"email": "ghost@sleepsense.app"})
        assert not any("reset-password" in r.message for r in caplog.records)


# ── /auth/reset-password ───────────────────────────────────────────────────────

def _get_reset_token(client, email, caplog) -> str:
    """Trigger forgot-password and extract the token from the log."""
    with caplog.at_level(logging.INFO, logger="app.routes.auth"):
        client.post("/auth/forgot-password", json={"email": email})
    log_msg = next(r.message for r in caplog.records if "reset-password" in r.message)
    return log_msg.split("token=")[1].strip()


class TestResetPassword:
    def test_valid_token_returns_200(self, client, registered_user, caplog):
        token = _get_reset_token(client, "aman@sleepsense.app", caplog)
        resp = client.post("/auth/reset-password", json={"token": token, "new_password": "NewPass456!"})
        assert resp.status_code == 200

    def test_allows_login_with_new_password(self, client, registered_user, caplog):
        token = _get_reset_token(client, "aman@sleepsense.app", caplog)
        client.post("/auth/reset-password", json={"token": token, "new_password": "NewPass456!"})

        resp = client.post("/auth/login", json={"email": "aman@sleepsense.app", "password": "NewPass456!"})
        assert resp.status_code == 200

    def test_rejects_old_password_after_reset(self, client, registered_user, caplog):
        token = _get_reset_token(client, "aman@sleepsense.app", caplog)
        client.post("/auth/reset-password", json={"token": token, "new_password": "NewPass456!"})

        resp = client.post("/auth/login", json={"email": "aman@sleepsense.app", "password": "Test1234!"})
        assert resp.status_code == 401

    def test_token_is_single_use(self, client, registered_user, caplog):
        token = _get_reset_token(client, "aman@sleepsense.app", caplog)
        client.post("/auth/reset-password", json={"token": token, "new_password": "NewPass456!"})

        resp = client.post("/auth/reset-password", json={"token": token, "new_password": "Another789!"})
        assert resp.status_code == 400

    def test_invalid_token_returns_400(self, client):
        resp = client.post("/auth/reset-password", json={"token": "fake-token", "new_password": "NewPass456!"})
        assert resp.status_code == 400

    def test_revokes_existing_refresh_tokens(self, client, registered_user, caplog):
        old_refresh = registered_user["refresh_token"]
        token = _get_reset_token(client, "aman@sleepsense.app", caplog)
        client.post("/auth/reset-password", json={"token": token, "new_password": "NewPass456!"})

        resp = client.post("/auth/refresh", json={"refresh_token": old_refresh})
        assert resp.status_code == 401

    def test_second_forgot_invalidates_first_token(self, client, registered_user, caplog):
        token1 = _get_reset_token(client, "aman@sleepsense.app", caplog)
        caplog.clear()
        token2 = _get_reset_token(client, "aman@sleepsense.app", caplog)

        # First token is now consumed (marked used by second forgot-password call)
        resp1 = client.post("/auth/reset-password", json={"token": token1, "new_password": "ShouldFail1!"})
        assert resp1.status_code == 400

        resp2 = client.post("/auth/reset-password", json={"token": token2, "new_password": "ShouldWork1!"})
        assert resp2.status_code == 200


# ── Login rate limiting ────────────────────────────────────────────────────────

class TestLoginRateLimit:
    def test_429_after_10_requests(self, client, registered_user):
        for _ in range(10):
            client.post("/auth/login", json={"email": "aman@sleepsense.app", "password": "Wrong!"})
        resp = client.post("/auth/login", json={"email": "aman@sleepsense.app", "password": "Wrong!"})
        assert resp.status_code == 429

    def test_429_response_has_detail(self, client, registered_user):
        for _ in range(10):
            client.post("/auth/login", json={"email": "aman@sleepsense.app", "password": "Wrong!"})
        resp = client.post("/auth/login", json={"email": "aman@sleepsense.app", "password": "Wrong!"})
        assert "Too many" in resp.json()["detail"]

    def test_10th_request_still_allowed(self, client, registered_user):
        for _ in range(9):
            client.post("/auth/login", json={"email": "aman@sleepsense.app", "password": "Wrong!"})
        resp = client.post("/auth/login", json={"email": "aman@sleepsense.app", "password": "Test1234!"})
        assert resp.status_code == 200

    def test_rate_limit_resets_between_tests(self, client, registered_user):
        # Each test starts fresh; a single valid login should succeed
        resp = client.post("/auth/login", json={"email": "aman@sleepsense.app", "password": "Test1234!"})
        assert resp.status_code == 200
