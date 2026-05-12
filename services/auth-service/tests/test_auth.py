"""
Tests for POST /auth/register, /auth/login, /auth/refresh, /auth/logout
and the password-hashing guarantee.
"""
import pytest
from app.security import hash_password, verify_password


# ── /auth/register ─────────────────────────────────────────────────────────────

class TestRegister:
    def test_register_success_returns_201_and_tokens(self, client):
        resp = client.post("/auth/register", json={
            "email": "new@sleepsense.app",
            "password": "Test1234!",
            "display_name": "New User",
        })
        assert resp.status_code == 201
        body = resp.json()
        assert "access_token" in body
        assert "refresh_token" in body
        assert body["token_type"] == "bearer"
        assert body["expires_in"] > 0

    def test_register_duplicate_email_returns_409(self, client):
        payload = {"email": "dup@sleepsense.app", "password": "Test1234!", "display_name": "A"}
        client.post("/auth/register", json=payload)
        resp = client.post("/auth/register", json=payload)
        assert resp.status_code == 409
        assert "already registered" in resp.json()["detail"]

    def test_register_invalid_email_returns_422(self, client):
        resp = client.post("/auth/register", json={
            "email": "not-an-email",
            "password": "Test1234!",
            "display_name": "User",
        })
        assert resp.status_code == 422

    def test_register_missing_fields_returns_422(self, client):
        resp = client.post("/auth/register", json={"email": "x@y.com"})
        assert resp.status_code == 422


# ── /auth/login ────────────────────────────────────────────────────────────────

class TestLogin:
    def test_login_success_returns_tokens(self, client, registered_user):
        resp = client.post("/auth/login", json={
            "email": "aman@sleepsense.app",
            "password": "Test1234!",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert "refresh_token" in body

    def test_login_wrong_password_returns_401(self, client, registered_user):
        resp = client.post("/auth/login", json={
            "email": "aman@sleepsense.app",
            "password": "WrongPassword!",
        })
        assert resp.status_code == 401
        assert "Invalid credentials" in resp.json()["detail"]

    def test_login_unknown_email_returns_401(self, client):
        resp = client.post("/auth/login", json={
            "email": "ghost@sleepsense.app",
            "password": "Test1234!",
        })
        assert resp.status_code == 401

    def test_login_returns_different_token_each_time(self, client, registered_user):
        creds = {"email": "aman@sleepsense.app", "password": "Test1234!"}
        token_a = client.post("/auth/login", json=creds).json()["access_token"]
        token_b = client.post("/auth/login", json=creds).json()["access_token"]
        # Two separate logins produce two separate tokens (different exp timestamps)
        assert token_a != token_b


# ── /auth/refresh ──────────────────────────────────────────────────────────────

class TestRefresh:
    def test_refresh_returns_new_access_token(self, client, registered_user):
        refresh_token = registered_user["refresh_token"]
        resp = client.post("/auth/refresh", json={"refresh_token": refresh_token})
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert "refresh_token" in body

    def test_refresh_rotates_token(self, client, registered_user):
        """Old refresh token must be rejected after rotation."""
        old_refresh = registered_user["refresh_token"]
        new_tokens = client.post("/auth/refresh", json={"refresh_token": old_refresh}).json()

        # Old token is now consumed — reusing it must fail
        resp = client.post("/auth/refresh", json={"refresh_token": old_refresh})
        assert resp.status_code == 401

        # New token must still work
        resp2 = client.post("/auth/refresh", json={"refresh_token": new_tokens["refresh_token"]})
        assert resp2.status_code == 200

    def test_refresh_with_invalid_token_returns_401(self, client):
        resp = client.post("/auth/refresh", json={"refresh_token": "totally.invalid.token"})
        assert resp.status_code == 401

    def test_refresh_with_access_token_returns_401(self, client, registered_user):
        """Passing an access token where a refresh token is expected must fail."""
        resp = client.post("/auth/refresh", json={"refresh_token": registered_user["access_token"]})
        assert resp.status_code == 401


# ── /auth/logout ───────────────────────────────────────────────────────────────

class TestLogout:
    def test_logout_invalidates_refresh_token(self, client, registered_user):
        refresh_token = registered_user["refresh_token"]

        logout_resp = client.post("/auth/logout", json={"refresh_token": refresh_token})
        assert logout_resp.status_code == 200

        # Refresh after logout must fail
        resp = client.post("/auth/refresh", json={"refresh_token": refresh_token})
        assert resp.status_code == 401

    def test_logout_with_unknown_token_returns_200(self, client):
        # Logout is idempotent — revoking a non-existent token should not crash
        resp = client.post("/auth/logout", json={"refresh_token": "unknown.token.here"})
        assert resp.status_code == 200


# ── Password hashing ───────────────────────────────────────────────────────────

class TestPasswordHashing:
    def test_hash_is_not_plaintext(self):
        plain = "MySecret123!"
        hashed = hash_password(plain)
        assert hashed != plain

    def test_hash_starts_with_bcrypt_prefix(self):
        hashed = hash_password("password")
        assert hashed.startswith("$2b$")

    def test_verify_correct_password(self):
        plain = "CorrectPassword!"
        assert verify_password(plain, hash_password(plain)) is True

    def test_verify_wrong_password(self):
        assert verify_password("WrongPassword!", hash_password("CorrectPassword!")) is False

    def test_same_password_produces_different_hashes(self):
        # bcrypt generates a unique salt every time
        h1 = hash_password("same_password")
        h2 = hash_password("same_password")
        assert h1 != h2

    def test_both_hashes_verify_correctly(self):
        plain = "same_password"
        h1 = hash_password(plain)
        h2 = hash_password(plain)
        assert verify_password(plain, h1) is True
        assert verify_password(plain, h2) is True
