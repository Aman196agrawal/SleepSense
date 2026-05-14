"""
Tests for GET /users/me and PATCH /users/me.
"""


class TestGetMe:
    def test_get_me_returns_user_profile(self, client, registered_user, auth_headers):
        resp = client.get("/users/me", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["email"] == "aman@sleepsense.app"
        assert body["display_name"] == "Aman"
        assert "id" in body
        assert "created_at" in body
        # Password must never be exposed
        assert "password" not in body
        assert "password_hash" not in body

    def test_get_me_without_token_returns_401(self, client):
        resp = client.get("/users/me")
        assert resp.status_code == 401

    def test_get_me_with_invalid_token_returns_401(self, client):
        resp = client.get("/users/me", headers={"Authorization": "Bearer bad.token.here"})
        assert resp.status_code == 401

    def test_get_me_with_malformed_header_returns_401(self, client):
        resp = client.get("/users/me", headers={"Authorization": "NotBearer token"})
        assert resp.status_code == 401


class TestUpdateMe:
    def test_update_display_name(self, client, auth_headers):
        resp = client.patch("/users/me", json={"display_name": "Updated Name"}, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["display_name"] == "Updated Name"

    def test_update_weight_and_height(self, client, auth_headers):
        resp = client.patch("/users/me", json={"weight_kg": "75", "height_cm": "175"}, headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["weight_kg"] == "75"
        assert body["height_cm"] == "175"

    def test_update_timezone(self, client, auth_headers):
        resp = client.patch("/users/me", json={"timezone": "America/New_York"}, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["timezone"] == "America/New_York"

    def test_partial_update_does_not_clear_other_fields(self, client, auth_headers):
        client.patch("/users/me", json={"weight_kg": "70"}, headers=auth_headers)
        resp = client.patch("/users/me", json={"height_cm": "180"}, headers=auth_headers)
        body = resp.json()
        assert body["weight_kg"] == "70"
        assert body["height_cm"] == "180"

    def test_update_without_token_returns_401(self, client):
        resp = client.patch("/users/me", json={"display_name": "Hacker"})
        assert resp.status_code == 401

    def test_updated_profile_visible_on_get_me(self, client, auth_headers):
        client.patch("/users/me", json={"display_name": "Final Name"}, headers=auth_headers)
        resp = client.get("/users/me", headers=auth_headers)
        assert resp.json()["display_name"] == "Final Name"
