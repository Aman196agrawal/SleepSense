"""Tests for insight HTTP routes — generate, get, mark-read."""
from unittest.mock import patch

import pytest

from tests.conftest import (
    OTHER_USER_ID,
    SESSION_ID,
    TEST_USER_ID,
    chronic_snoring_payload,
    good_session_payload,
    make_insight,
)


# ── POST /insights/generate ───────────────────────────────────────────────────

class TestGenerateInsights:
    def test_good_session_returns_200(self, client):
        r = client.post("/insights/generate", json=good_session_payload())
        assert r.status_code == 200

    def test_good_session_no_rules_fire(self, client):
        r = client.post("/insights/generate", json=good_session_payload())
        assert r.json() == []

    def test_chronic_session_returns_insights(self, client):
        r = client.post("/insights/generate", json=chronic_snoring_payload())
        assert len(r.json()) >= 1

    def test_insights_stored_in_db(self, client, db):
        client.post("/insights/generate", json=chronic_snoring_payload())
        from app.models import SessionInsight
        count = db.query(SessionInsight).count()
        assert count >= 1

    def test_response_fields_present(self, client):
        # Use a payload that fires POSITIONAL_SNORING
        payload = good_session_payload()
        payload["sleep_position"] = "back"
        payload["snore_ratio"] = 0.6
        r = client.post("/insights/generate", json=payload)
        if r.json():
            item = r.json()[0]
            for field in ("id", "session_id", "insight_type", "priority", "title", "body", "action_url", "is_read"):
                assert field in item

    def test_is_read_false_on_creation(self, client):
        payload = good_session_payload()
        payload["sleep_position"] = "back"
        payload["snore_ratio"] = 0.6
        r = client.post("/insights/generate", json=payload)
        for item in r.json():
            assert item["is_read"] is False

    def test_session_id_stored_correctly(self, client, db):
        payload = good_session_payload(session_id="my-session-xyz")
        payload["sleep_position"] = "back"
        payload["snore_ratio"] = 0.6
        client.post("/insights/generate", json=payload)
        from app.models import SessionInsight
        ins = db.query(SessionInsight).filter_by(session_id="my-session-xyz").first()
        assert ins is not None

    def test_at_most_three_returned(self, client):
        # Trigger multiple rules
        payload = {
            "session_id":          SESSION_ID,
            "sleep_quality_score": 40.0,
            "snore_ratio":         0.7,
            "avg_snore_intensity": 80.0,
            "duration_minutes":    480,
            "recent_scores":       [45.0, 42.0, 38.0, 41.0],
            "recent_durations":    [300, 310, 320, 420, 410],
            "alcohol_units_today": 2.0,
            "sleep_position":      "back",
        }
        r = client.post("/insights/generate", json=payload)
        assert len(r.json()) <= 3

    def test_chronic_snoring_emits_kafka_notification(self, client):
        with patch("app.kafka_producer.emit") as mock_emit:
            client.post("/insights/generate", json=chronic_snoring_payload())
        # Should have emitted notification.send for CHRONIC_SNORING
        calls = [c for c in mock_emit.call_args_list if c[0][0] == "notification.send"]
        assert len(calls) >= 1

    def test_good_session_does_not_emit_kafka(self, client):
        with patch("app.kafka_producer.emit") as mock_emit:
            client.post("/insights/generate", json=good_session_payload())
        mock_emit.assert_not_called()

    def test_no_auth_returns_401(self, db):
        from unittest.mock import patch as p
        from fastapi.testclient import TestClient
        from app.main import app
        with p("app.main.init_db"), TestClient(app) as bare:
            r = bare.post("/insights/generate", json=good_session_payload())
        assert r.status_code in (401, 403)


# ── GET /insights?session_id=... ─────────────────────────────────────────────

class TestGetInsights:
    def test_returns_200_empty_list(self, client):
        r = client.get("/insights", params={"session_id": "nonexistent-session"})
        assert r.status_code == 200
        assert r.json() == []

    def test_returns_stored_insights(self, client, db):
        make_insight(db, session_id=SESSION_ID, priority=8)
        r = client.get("/insights", params={"session_id": SESSION_ID})
        assert len(r.json()) == 1

    def test_returns_at_most_three(self, client, db):
        for p in (9, 8, 7, 6, 5):
            make_insight(db, session_id=SESSION_ID, priority=p, title=f"Insight {p}")
        r = client.get("/insights", params={"session_id": SESSION_ID})
        assert len(r.json()) == 3

    def test_sorted_by_priority_descending(self, client, db):
        make_insight(db, session_id=SESSION_ID, priority=5, title="Low")
        make_insight(db, session_id=SESSION_ID, priority=9, title="High")
        make_insight(db, session_id=SESSION_ID, priority=7, title="Mid")
        items = client.get("/insights", params={"session_id": SESSION_ID}).json()
        priorities = [i["priority"] for i in items]
        assert priorities == sorted(priorities, reverse=True)

    def test_only_own_session_returned(self, client, db):
        make_insight(db, session_id="other-session", user_id=OTHER_USER_ID, priority=9)
        r = client.get("/insights", params={"session_id": "other-session"})
        assert r.json() == []

    def test_session_id_required(self, client):
        r = client.get("/insights")
        assert r.status_code == 422

    def test_response_fields_present(self, client, db):
        make_insight(db, session_id=SESSION_ID)
        item = client.get("/insights", params={"session_id": SESSION_ID}).json()[0]
        for field in ("id", "session_id", "insight_type", "priority", "title", "body", "action_url", "is_read", "created_at"):
            assert field in item

    def test_no_auth_returns_401(self, db):
        from unittest.mock import patch as p
        from fastapi.testclient import TestClient
        from app.main import app
        with p("app.main.init_db"), TestClient(app) as bare:
            r = bare.get("/insights", params={"session_id": SESSION_ID})
        assert r.status_code in (401, 403)


# ── PATCH /insights/{id}/read ─────────────────────────────────────────────────

class TestMarkRead:
    def test_marks_insight_as_read(self, client, db):
        ins = make_insight(db, is_read=False)
        r = client.patch(f"/insights/{ins.id}/read")
        assert r.status_code == 200
        assert r.json()["is_read"] is True

    def test_idempotent_already_read(self, client, db):
        ins = make_insight(db, is_read=True)
        r = client.patch(f"/insights/{ins.id}/read")
        assert r.status_code == 200
        assert r.json()["is_read"] is True

    def test_not_found_returns_200_with_is_read_true(self, client):
        r = client.patch("/insights/nonexistent-id/read")
        assert r.status_code == 200
        assert r.json()["is_read"] is True

    def test_wrong_user_returns_403(self, client, db):
        ins = make_insight(db, user_id=OTHER_USER_ID)
        r = client.patch(f"/insights/{ins.id}/read")
        assert r.status_code == 403

    def test_response_contains_id(self, client, db):
        ins = make_insight(db)
        data = client.patch(f"/insights/{ins.id}/read").json()
        assert data["id"] == ins.id

    def test_persisted_in_db(self, client, db):
        from app.models import SessionInsight
        ins = make_insight(db, is_read=False)
        client.patch(f"/insights/{ins.id}/read")
        db.refresh(ins)
        assert ins.is_read is True


# ── GET /health ───────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_ok(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_health_service_name(self, client):
        r = client.get("/health")
        assert "insight-engine" in r.json()["service"]
