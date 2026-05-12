"""
Tests for GET /users/me/health-profile and PUT /users/me/health-profile.
"""


class TestGetHealthProfile:
    def test_get_requires_token(self, client):
        resp = client.get("/users/me/health-profile")
        assert resp.status_code == 401

    def test_get_returns_200_when_no_profile_set(self, client, auth_headers):
        resp = client.get("/users/me/health-profile", headers=auth_headers)
        assert resp.status_code == 200

    def test_get_all_fields_null_when_no_profile(self, client, auth_headers):
        body = client.get("/users/me/health-profile", headers=auth_headers).json()
        assert body["sleep_position"] is None
        assert body["known_conditions"] is None
        assert body["medications"] is None
        assert body["alcohol_frequency"] is None
        assert body["smoking_status"] is None
        assert body["cpap_user"] is None
        assert body["snoring_severity_self"] is None

    def test_get_reflects_saved_profile(self, client, auth_headers):
        client.put("/users/me/health-profile", json={
            "sleep_position": "side",
            "cpap_user": True,
            "snoring_severity_self": 3,
        }, headers=auth_headers)
        body = client.get("/users/me/health-profile", headers=auth_headers).json()
        assert body["sleep_position"] == "side"
        assert body["cpap_user"] is True
        assert body["snoring_severity_self"] == 3


class TestPutHealthProfile:
    def test_put_requires_token(self, client):
        resp = client.put("/users/me/health-profile", json={})
        assert resp.status_code == 401

    def test_put_empty_body_returns_200(self, client, auth_headers):
        resp = client.put("/users/me/health-profile", json={}, headers=auth_headers)
        assert resp.status_code == 200

    def test_put_saves_sleep_position(self, client, auth_headers):
        body = client.put("/users/me/health-profile", json={"sleep_position": "stomach"}, headers=auth_headers).json()
        assert body["sleep_position"] == "stomach"

    def test_put_saves_all_scalar_fields(self, client, auth_headers):
        payload = {
            "sleep_position": "back",
            "alcohol_frequency": "occasionally",
            "smoking_status": "former",
            "cpap_user": False,
            "snoring_severity_self": 4,
        }
        body = client.put("/users/me/health-profile", json=payload, headers=auth_headers).json()
        assert body["sleep_position"] == "back"
        assert body["alcohol_frequency"] == "occasionally"
        assert body["smoking_status"] == "former"
        assert body["cpap_user"] is False
        assert body["snoring_severity_self"] == 4

    def test_put_saves_known_conditions_list(self, client, auth_headers):
        body = client.put("/users/me/health-profile", json={
            "known_conditions": ["asthma", "obesity"],
        }, headers=auth_headers).json()
        assert body["known_conditions"] == ["asthma", "obesity"]

    def test_put_saves_medications_list(self, client, auth_headers):
        body = client.put("/users/me/health-profile", json={
            "medications": ["metformin", "lisinopril"],
        }, headers=auth_headers).json()
        assert body["medications"] == ["metformin", "lisinopril"]

    def test_put_empty_conditions_list_saves_correctly(self, client, auth_headers):
        body = client.put("/users/me/health-profile", json={"known_conditions": []}, headers=auth_headers).json()
        assert body["known_conditions"] == []

    def test_put_upserts_on_second_call(self, client, auth_headers):
        client.put("/users/me/health-profile", json={"sleep_position": "back"}, headers=auth_headers)
        client.put("/users/me/health-profile", json={"sleep_position": "side"}, headers=auth_headers)
        body = client.get("/users/me/health-profile", headers=auth_headers).json()
        assert body["sleep_position"] == "side"

    def test_put_returns_updated_at(self, client, auth_headers):
        body = client.put("/users/me/health-profile", json={"cpap_user": True}, headers=auth_headers).json()
        assert "updated_at" in body
        assert body["updated_at"] is not None

    def test_put_invalid_sleep_position_returns_422(self, client, auth_headers):
        resp = client.put("/users/me/health-profile", json={"sleep_position": "floating"}, headers=auth_headers)
        assert resp.status_code == 422

    def test_put_invalid_alcohol_frequency_returns_422(self, client, auth_headers):
        resp = client.put("/users/me/health-profile", json={"alcohol_frequency": "daily"}, headers=auth_headers)
        assert resp.status_code == 422

    def test_put_invalid_smoking_status_returns_422(self, client, auth_headers):
        resp = client.put("/users/me/health-profile", json={"smoking_status": "sometimes"}, headers=auth_headers)
        assert resp.status_code == 422

    def test_put_snoring_severity_below_1_returns_422(self, client, auth_headers):
        resp = client.put("/users/me/health-profile", json={"snoring_severity_self": 0}, headers=auth_headers)
        assert resp.status_code == 422

    def test_put_snoring_severity_above_5_returns_422(self, client, auth_headers):
        resp = client.put("/users/me/health-profile", json={"snoring_severity_self": 6}, headers=auth_headers)
        assert resp.status_code == 422

    def test_put_snoring_severity_boundary_1_is_valid(self, client, auth_headers):
        resp = client.put("/users/me/health-profile", json={"snoring_severity_self": 1}, headers=auth_headers)
        assert resp.status_code == 200

    def test_put_snoring_severity_boundary_5_is_valid(self, client, auth_headers):
        resp = client.put("/users/me/health-profile", json={"snoring_severity_self": 5}, headers=auth_headers)
        assert resp.status_code == 200

    def test_put_user_isolation(self, client, auth_headers):
        client.put("/users/me/health-profile", json={"sleep_position": "back"}, headers=auth_headers)

        r2 = client.post("/auth/register", json={
            "email": "user2@sleepsense.app",
            "password": "Test1234!",
            "display_name": "User2",
        })
        headers_2 = {"Authorization": f"Bearer {r2.json()['access_token']}"}
        body_2 = client.get("/users/me/health-profile", headers=headers_2).json()
        assert body_2["sleep_position"] is None
