"""
Tests for lifestyle routes:
  POST /lifestyle               — log / upsert
  GET  /lifestyle               — list with day window
  GET  /lifestyle/correlations  — lifestyle × sleep correlations
"""
from datetime import date, timedelta

TODAY = date.today().isoformat()
YESTERDAY = (date.today() - timedelta(days=1)).isoformat()
OLD_DATE = "2000-01-01"

LOG_BASE = {
    "logged_date": TODAY,
    "caffeine_cups": 2,
    "alcohol_units": 1.0,
    "exercise_minutes": 30,
    "stress_level": 3,
    "sleep_aid_used": False,
}


class TestLogLifestyle:
    def test_log_requires_token(self, client):
        resp = client.post("/lifestyle", json=LOG_BASE)
        assert resp.status_code == 401

    def test_log_returns_201(self, client, headers_a):
        resp = client.post("/lifestyle", json=LOG_BASE, headers=headers_a)
        assert resp.status_code == 201

    def test_log_returns_all_required_fields(self, client, headers_a):
        body = client.post("/lifestyle", json=LOG_BASE, headers=headers_a).json()
        required = {
            "id", "logged_date", "caffeine_cups", "alcohol_units",
            "exercise_minutes", "stress_level", "sleep_aid_used", "notes", "created_at",
        }
        assert required.issubset(body.keys())

    def test_log_values_match_input(self, client, headers_a):
        body = client.post("/lifestyle", json=LOG_BASE, headers=headers_a).json()
        assert body["logged_date"] == TODAY
        assert body["caffeine_cups"] == 2
        assert body["alcohol_units"] == 1.0
        assert body["exercise_minutes"] == 30
        assert body["stress_level"] == 3
        assert body["sleep_aid_used"] is False

    def test_log_notes_saved_and_returned(self, client, headers_a):
        payload = {**LOG_BASE, "notes": "had a late coffee"}
        body = client.post("/lifestyle", json=payload, headers=headers_a).json()
        assert body["notes"] == "had a late coffee"

    def test_log_notes_null_when_omitted(self, client, headers_a):
        body = client.post("/lifestyle", json=LOG_BASE, headers=headers_a).json()
        assert body["notes"] is None

    def test_log_defaults_when_only_date_given(self, client, headers_a):
        body = client.post("/lifestyle", json={"logged_date": TODAY}, headers=headers_a).json()
        assert body["caffeine_cups"] == 0
        assert body["alcohol_units"] == 0.0
        assert body["exercise_minutes"] == 0
        assert body["stress_level"] == 3
        assert body["sleep_aid_used"] is False

    def test_log_upserts_same_date(self, client, headers_a):
        client.post("/lifestyle", json={**LOG_BASE, "caffeine_cups": 1}, headers=headers_a)
        client.post("/lifestyle", json={**LOG_BASE, "caffeine_cups": 4}, headers=headers_a)
        logs = client.get("/lifestyle?days=36500", headers=headers_a).json()
        today_logs = [l for l in logs if l["logged_date"] == TODAY]
        assert len(today_logs) == 1
        assert today_logs[0]["caffeine_cups"] == 4

    def test_log_upsert_replaces_all_fields(self, client, headers_a):
        client.post("/lifestyle", json={**LOG_BASE, "notes": "original"}, headers=headers_a)
        client.post("/lifestyle", json={**LOG_BASE, "notes": "updated"}, headers=headers_a)
        logs = client.get("/lifestyle?days=36500", headers=headers_a).json()
        today_logs = [l for l in logs if l["logged_date"] == TODAY]
        assert today_logs[0]["notes"] == "updated"

    def test_log_caffeine_above_max_returns_422(self, client, headers_a):
        resp = client.post("/lifestyle", json={**LOG_BASE, "caffeine_cups": 11}, headers=headers_a)
        assert resp.status_code == 422

    def test_log_stress_below_min_returns_422(self, client, headers_a):
        resp = client.post("/lifestyle", json={**LOG_BASE, "stress_level": 0}, headers=headers_a)
        assert resp.status_code == 422

    def test_log_stress_above_max_returns_422(self, client, headers_a):
        resp = client.post("/lifestyle", json={**LOG_BASE, "stress_level": 6}, headers=headers_a)
        assert resp.status_code == 422

    def test_log_exercise_above_max_returns_422(self, client, headers_a):
        resp = client.post("/lifestyle", json={**LOG_BASE, "exercise_minutes": 301}, headers=headers_a)
        assert resp.status_code == 422

    def test_log_alcohol_above_max_returns_422(self, client, headers_a):
        resp = client.post("/lifestyle", json={**LOG_BASE, "alcohol_units": 21.0}, headers=headers_a)
        assert resp.status_code == 422


class TestGetLogs:
    def test_get_logs_requires_token(self, client):
        resp = client.get("/lifestyle")
        assert resp.status_code == 401

    def test_get_logs_returns_list(self, client, headers_a):
        resp = client.get("/lifestyle", headers=headers_a)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_logs_empty_when_nothing_logged(self, client, headers_a):
        assert client.get("/lifestyle", headers=headers_a).json() == []

    def test_get_logs_contains_created_log(self, client, headers_a):
        client.post("/lifestyle", json=LOG_BASE, headers=headers_a)
        logs = client.get("/lifestyle", headers=headers_a).json()
        assert len(logs) == 1
        assert logs[0]["logged_date"] == TODAY

    def test_get_logs_excludes_dates_outside_window(self, client, headers_a):
        client.post("/lifestyle", json={**LOG_BASE, "logged_date": OLD_DATE}, headers=headers_a)
        logs = client.get("/lifestyle", headers=headers_a).json()  # default 14 days
        assert all(l["logged_date"] != OLD_DATE for l in logs)

    def test_get_logs_custom_days_includes_old_date(self, client, headers_a):
        client.post("/lifestyle", json={**LOG_BASE, "logged_date": OLD_DATE}, headers=headers_a)
        logs = client.get("/lifestyle?days=36500", headers=headers_a).json()
        assert any(l["logged_date"] == OLD_DATE for l in logs)

    def test_get_logs_ordered_newest_first(self, client, headers_a):
        client.post("/lifestyle", json={**LOG_BASE, "logged_date": YESTERDAY}, headers=headers_a)
        client.post("/lifestyle", json={**LOG_BASE, "logged_date": TODAY}, headers=headers_a)
        logs = client.get("/lifestyle", headers=headers_a).json()
        dates = [l["logged_date"] for l in logs]
        assert dates == sorted(dates, reverse=True)

    def test_get_logs_multiple_dates_all_returned(self, client, headers_a):
        client.post("/lifestyle", json={**LOG_BASE, "logged_date": TODAY}, headers=headers_a)
        client.post("/lifestyle", json={**LOG_BASE, "logged_date": YESTERDAY}, headers=headers_a)
        logs = client.get("/lifestyle", headers=headers_a).json()
        assert len(logs) == 2

    def test_get_logs_user_isolation(self, client, headers_a, headers_b):
        client.post("/lifestyle", json=LOG_BASE, headers=headers_a)
        logs_b = client.get("/lifestyle", headers=headers_b).json()
        assert logs_b == []


class TestCorrelations:
    def test_correlations_requires_token(self, client):
        resp = client.get("/lifestyle/correlations")
        assert resp.status_code == 401

    def test_correlations_returns_200(self, client, headers_a):
        resp = client.get("/lifestyle/correlations", headers=headers_a)
        assert resp.status_code == 200

    def test_correlations_has_correlations_key(self, client, headers_a):
        body = client.get("/lifestyle/correlations", headers=headers_a).json()
        assert "correlations" in body

    def test_correlations_empty_when_no_data_at_all(self, client, headers_a):
        body = client.get("/lifestyle/correlations", headers=headers_a).json()
        assert body["correlations"] == []
        assert "message" in body

    def test_correlations_empty_when_no_sessions(self, client, headers_a):
        # Lifestyle logs exist but no sleep sessions → cannot compute correlations
        client.post("/lifestyle", json=LOG_BASE, headers=headers_a)
        body = client.get("/lifestyle/correlations", headers=headers_a).json()
        assert body["correlations"] == []

    def test_correlations_empty_when_no_lifestyle_logs(self, client, headers_a):
        # Sessions exist (via seeding) but no lifestyle logs → cannot compute correlations
        client.get("/analytics/trends", headers=headers_a)  # triggers seed_user
        body = client.get("/lifestyle/correlations", headers=headers_a).json()
        assert body["correlations"] == []

    def test_correlations_returns_list_when_both_data_present(self, client, headers_a):
        client.get("/analytics/trends", headers=headers_a)  # seed 30 days of sessions
        client.post("/lifestyle", json=LOG_BASE, headers=headers_a)
        body = client.get("/lifestyle/correlations", headers=headers_a).json()
        assert isinstance(body["correlations"], list)

    def test_correlations_items_have_required_fields(self, client, headers_a):
        client.get("/analytics/trends", headers=headers_a)
        # Log alcohol on multiple dates so the pattern engine has data to compute
        client.post("/lifestyle", json={**LOG_BASE, "logged_date": TODAY, "alcohol_units": 3.0}, headers=headers_a)
        client.post("/lifestyle", json={**LOG_BASE, "logged_date": YESTERDAY, "alcohol_units": 0.0}, headers=headers_a)
        correlations = client.get("/lifestyle/correlations", headers=headers_a).json()["correlations"]
        for item in correlations:
            assert "title" in item
            assert "body" in item
            assert "type" in item

    def test_correlations_user_isolation(self, client, headers_a, headers_b):
        client.post("/lifestyle", json=LOG_BASE, headers=headers_a)
        body_b = client.get("/lifestyle/correlations", headers=headers_b).json()
        assert body_b["correlations"] == []
