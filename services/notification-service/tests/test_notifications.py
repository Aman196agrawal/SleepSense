"""Tests for GET /notifications, PATCH /notifications/{id}/read, POST /notifications/mark-all-read."""
import pytest

from tests.conftest import OTHER_USER_ID, TEST_USER_ID, make_notification


# ── GET /notifications ────────────────────────────────────────────────────────

class TestListNotifications:
    def test_empty_returns_zero_total(self, client):
        r = client.get("/notifications")
        assert r.status_code == 200
        assert r.json()["total"] == 0
        assert r.json()["notifications"] == []

    def test_own_notification_returned(self, client, db):
        make_notification(db)
        r = client.get("/notifications")
        assert r.json()["total"] == 1
        assert len(r.json()["notifications"]) == 1

    def test_other_user_notification_excluded(self, client, db):
        make_notification(db, user_id=OTHER_USER_ID)
        r = client.get("/notifications")
        assert r.json()["total"] == 0

    def test_multiple_returned_latest_first(self, client, db):
        for i in range(3):
            make_notification(db, title=f"Notif {i}")
        items = client.get("/notifications").json()["notifications"]
        assert len(items) == 3
        # created_at descending — latest created_at first
        dates = [n["created_at"] for n in items]
        assert dates == sorted(dates, reverse=True)

    def test_limit_respected(self, client, db):
        for _ in range(5):
            make_notification(db)
        r = client.get("/notifications?limit=2")
        assert len(r.json()["notifications"]) == 2
        assert r.json()["total"] == 5

    def test_offset_respected(self, client, db):
        for _ in range(4):
            make_notification(db)
        r1 = client.get("/notifications?limit=2&offset=0").json()["notifications"]
        r2 = client.get("/notifications?limit=2&offset=2").json()["notifications"]
        ids1 = {n["id"] for n in r1}
        ids2 = {n["id"] for n in r2}
        assert ids1.isdisjoint(ids2)

    def test_notification_fields_present(self, client, db):
        make_notification(db)
        item = client.get("/notifications").json()["notifications"][0]
        for field in ("id", "type", "title", "body", "payload", "channel", "is_read", "created_at"):
            assert field in item

    def test_payload_is_dict(self, client, db):
        make_notification(db)
        item = client.get("/notifications").json()["notifications"][0]
        assert isinstance(item["payload"], dict)

    def test_no_auth_returns_401(self, db):
        from unittest.mock import patch
        from fastapi.testclient import TestClient
        from app.main import app
        with patch("app.main.init_db"), TestClient(app) as bare:
            r = bare.get("/notifications")
        assert r.status_code in (401, 403)


# ── GET /notifications/unread-count ───────────────────────────────────────────

class TestUnreadCount:
    def test_zero_when_empty(self, client):
        r = client.get("/notifications/unread-count")
        assert r.status_code == 200
        assert r.json()["unread_count"] == 0

    def test_counts_unread(self, client, db):
        make_notification(db, is_read=False)
        make_notification(db, is_read=False)
        make_notification(db, is_read=True)
        assert client.get("/notifications/unread-count").json()["unread_count"] == 2

    def test_other_user_not_counted(self, client, db):
        make_notification(db, user_id=OTHER_USER_ID, is_read=False)
        assert client.get("/notifications/unread-count").json()["unread_count"] == 0

    def test_decrements_after_mark_read(self, client, db):
        n = make_notification(db, is_read=False)
        assert client.get("/notifications/unread-count").json()["unread_count"] == 1
        client.patch(f"/notifications/{n.id}/read")
        assert client.get("/notifications/unread-count").json()["unread_count"] == 0


# ── PATCH /notifications/{id}/read ───────────────────────────────────────────

class TestMarkRead:
    def test_marks_as_read(self, client, db):
        n = make_notification(db, is_read=False)
        r = client.patch(f"/notifications/{n.id}/read")
        assert r.status_code == 200
        assert r.json()["is_read"] is True

    def test_idempotent_already_read(self, client, db):
        n = make_notification(db, is_read=True)
        r = client.patch(f"/notifications/{n.id}/read")
        assert r.status_code == 200
        assert r.json()["is_read"] is True

    def test_not_found_returns_404(self, client):
        r = client.patch("/notifications/nonexistent-id/read")
        assert r.status_code == 404

    def test_wrong_user_returns_403(self, client, db):
        n = make_notification(db, user_id=OTHER_USER_ID)
        r = client.patch(f"/notifications/{n.id}/read")
        assert r.status_code == 403

    def test_response_contains_all_fields(self, client, db):
        n = make_notification(db)
        data = client.patch(f"/notifications/{n.id}/read").json()
        assert data["id"] == n.id
        assert data["title"] == n.title


# ── POST /notifications/mark-all-read ────────────────────────────────────────

class TestMarkAllRead:
    def test_marks_all_own_unread(self, client, db):
        for _ in range(3):
            make_notification(db, is_read=False)
        r = client.post("/notifications/mark-all-read")
        assert r.status_code == 200
        assert r.json()["marked_read"] == 3

    def test_returns_zero_when_all_already_read(self, client, db):
        for _ in range(2):
            make_notification(db, is_read=True)
        r = client.post("/notifications/mark-all-read")
        assert r.json()["marked_read"] == 0

    def test_does_not_touch_other_user(self, client, db):
        make_notification(db, user_id=OTHER_USER_ID, is_read=False)
        r = client.post("/notifications/mark-all-read")
        assert r.json()["marked_read"] == 0
        # other user's notification still unread
        from app.models import Notification
        other = db.query(Notification).filter_by(user_id=OTHER_USER_ID).first()
        assert other.is_read is False

    def test_unread_count_zero_after_bulk_mark(self, client, db):
        for _ in range(4):
            make_notification(db, is_read=False)
        client.post("/notifications/mark-all-read")
        assert client.get("/notifications/unread-count").json()["unread_count"] == 0
