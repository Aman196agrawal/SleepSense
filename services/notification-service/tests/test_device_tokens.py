"""Tests for POST/GET/DELETE /device-tokens."""
import pytest

from tests.conftest import OTHER_USER_ID, TEST_USER_ID, make_device_token


# ── POST /device-tokens ───────────────────────────────────────────────────────

class TestRegisterToken:
    def test_register_fcm(self, client):
        r = client.post("/device-tokens", json={"token": "fcm-tok-001", "platform": "fcm"})
        assert r.status_code == 200
        assert r.json()["platform"] == "fcm"
        assert r.json()["token"] == "fcm-tok-001"

    def test_register_apns(self, client):
        r = client.post("/device-tokens", json={"token": "apns-tok-001", "platform": "apns"})
        assert r.status_code == 200
        assert r.json()["platform"] == "apns"

    def test_response_has_id_and_created_at(self, client):
        r = client.post("/device-tokens", json={"token": "tok-xyz", "platform": "fcm"})
        data = r.json()
        assert "id" in data
        assert "created_at" in data

    def test_duplicate_token_is_idempotent(self, client):
        body = {"token": "tok-dup", "platform": "fcm"}
        r1 = client.post("/device-tokens", json=body)
        r2 = client.post("/device-tokens", json=body)
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.json()["id"] == r2.json()["id"]

    def test_invalid_platform_returns_422(self, client):
        r = client.post("/device-tokens", json={"token": "tok-bad", "platform": "windows"})
        assert r.status_code == 422

    def test_missing_token_returns_422(self, client):
        r = client.post("/device-tokens", json={"platform": "fcm"})
        assert r.status_code == 422

    def test_missing_platform_returns_422(self, client):
        r = client.post("/device-tokens", json={"token": "tok-noplat"})
        assert r.status_code == 422

    def test_no_auth_returns_401(self, db):
        from unittest.mock import patch
        from fastapi.testclient import TestClient
        from app.main import app
        with patch("app.main.init_db"), TestClient(app) as bare:
            r = bare.post("/device-tokens", json={"token": "t", "platform": "fcm"})
        assert r.status_code in (401, 403)


# ── GET /device-tokens ────────────────────────────────────────────────────────

class TestListDeviceTokens:
    def test_empty_list(self, client):
        r = client.get("/device-tokens")
        assert r.status_code == 200
        assert r.json()["tokens"] == []

    def test_own_tokens_returned(self, client, db):
        make_device_token(db, token="tok-a")
        make_device_token(db, token="tok-b")
        r = client.get("/device-tokens")
        assert len(r.json()["tokens"]) == 2

    def test_other_user_tokens_excluded(self, client, db):
        make_device_token(db, user_id=OTHER_USER_ID, token="other-tok")
        r = client.get("/device-tokens")
        assert r.json()["tokens"] == []

    def test_token_fields_present(self, client, db):
        make_device_token(db)
        tok = client.get("/device-tokens").json()["tokens"][0]
        for field in ("id", "token", "platform", "created_at"):
            assert field in tok


# ── DELETE /device-tokens/{token} ────────────────────────────────────────────

class TestUnregisterToken:
    def test_delete_own_token_204(self, client, db):
        dt = make_device_token(db, token="tok-del")
        r = client.delete(f"/device-tokens/{dt.token}")
        assert r.status_code == 204

    def test_token_gone_after_delete(self, client, db):
        dt = make_device_token(db, token="tok-gone")
        client.delete(f"/device-tokens/{dt.token}")
        assert client.get("/device-tokens").json()["tokens"] == []

    def test_not_found_returns_404(self, client):
        r = client.delete("/device-tokens/nonexistent-token-xyz")
        assert r.status_code == 404

    def test_wrong_user_returns_403(self, client, db):
        dt = make_device_token(db, user_id=OTHER_USER_ID, token="tok-other")
        r = client.delete(f"/device-tokens/{dt.token}")
        assert r.status_code == 403

    def test_double_delete_returns_404(self, client, db):
        dt = make_device_token(db, token="tok-dbl")
        client.delete(f"/device-tokens/{dt.token}")
        r = client.delete(f"/device-tokens/{dt.token}")
        assert r.status_code == 404
