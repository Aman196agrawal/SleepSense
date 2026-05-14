"""Tests for app/dispatcher.py — dispatch() creates records and routes to channels."""
import json
from unittest.mock import patch, MagicMock

import pytest

from app.dispatcher import dispatch
from app.models import Notification
from tests.conftest import TEST_USER_ID, make_device_token


# ── Record creation ───────────────────────────────────────────────────────────

class TestDispatchRecordCreation:
    def test_creates_notification_in_db(self, db):
        dispatch(
            user_id=TEST_USER_ID,
            notif_type="sleep_report_ready",
            title="Report ready",
            body="Tap to view",
            channels=["in_app"],
            db=db,
        )
        assert db.query(Notification).count() == 1

    def test_returns_notification_id(self, db):
        notif_id = dispatch(
            user_id=TEST_USER_ID,
            notif_type="sleep_report_ready",
            title="Report ready",
            body="Tap to view",
            channels=["in_app"],
            db=db,
        )
        assert isinstance(notif_id, str)
        assert len(notif_id) > 0

    def test_fields_stored_correctly(self, db):
        dispatch(
            user_id=TEST_USER_ID,
            notif_type="health_alert",
            title="Health Alert",
            body="5 poor nights detected.",
            channels=["push", "in_app"],
            db=db,
        )
        n = db.query(Notification).first()
        assert n.user_id    == TEST_USER_ID
        assert n.type       == "health_alert"
        assert n.title      == "Health Alert"
        assert n.body       == "5 poor nights detected."

    def test_payload_stored_as_json(self, db):
        dispatch(
            user_id=TEST_USER_ID,
            notif_type="achievement",
            title="Badge!",
            body="7-night streak",
            payload={"badge": "streak_7", "screen": "Achievements"},
            channels=["in_app"],
            db=db,
        )
        n = db.query(Notification).first()
        stored = json.loads(n.payload)
        assert stored["badge"] == "streak_7"

    def test_empty_payload_defaults_to_empty_dict(self, db):
        dispatch(
            user_id=TEST_USER_ID,
            notif_type="weekly_summary",
            title="Weekly",
            body="Your week in review.",
            channels=["in_app"],
            db=db,
        )
        n = db.query(Notification).first()
        assert json.loads(n.payload) == {}

    def test_channel_stored_as_comma_joined(self, db):
        dispatch(
            user_id=TEST_USER_ID,
            notif_type="generic",
            title="T",
            body="B",
            channels=["push", "in_app"],
            db=db,
        )
        n = db.query(Notification).first()
        assert "push" in n.channel
        assert "in_app" in n.channel

    def test_sent_at_set_for_in_app(self, db):
        dispatch(
            user_id=TEST_USER_ID,
            notif_type="generic",
            title="T",
            body="B",
            channels=["in_app"],
            db=db,
        )
        n = db.query(Notification).first()
        assert n.sent_at is not None


# ── Push channel ──────────────────────────────────────────────────────────────

class TestDispatchPushChannel:
    def test_push_channel_calls_send_push(self, db):
        with patch("app.push_client.send_push", return_value=1) as mock_push:
            dispatch(
                user_id=TEST_USER_ID,
                notif_type="sleep_report_ready",
                title="T",
                body="B",
                channels=["push"],
                db=db,
            )
        mock_push.assert_called_once()

    def test_push_channel_passes_correct_args(self, db):
        with patch("app.push_client.send_push", return_value=1) as mock_push:
            dispatch(
                user_id=TEST_USER_ID,
                notif_type="sleep_report_ready",
                title="My Title",
                body="My Body",
                payload={"k": "v"},
                channels=["push"],
                db=db,
            )
        args = mock_push.call_args
        assert args[0][0] == TEST_USER_ID
        assert args[0][1] == "My Title"
        assert args[0][2] == "My Body"
        assert args[0][3] == {"k": "v"}

    def test_push_with_no_tokens_still_creates_record(self, db):
        with patch("app.push_client.send_push", return_value=0):
            notif_id = dispatch(
                user_id=TEST_USER_ID,
                notif_type="sleep_report_ready",
                title="T",
                body="B",
                channels=["push", "in_app"],
                db=db,
            )
        assert db.query(Notification).filter_by(id=notif_id).first() is not None

    def test_in_app_channel_does_not_call_send_push(self, db):
        with patch("app.push_client.send_push") as mock_push:
            dispatch(
                user_id=TEST_USER_ID,
                notif_type="generic",
                title="T",
                body="B",
                channels=["in_app"],
                db=db,
            )
        mock_push.assert_not_called()


# ── Email channel ─────────────────────────────────────────────────────────────

class TestDispatchEmailChannel:
    def test_email_channel_calls_send_email(self, db):
        with patch("app.email_client.send_email", return_value=True) as mock_email:
            dispatch(
                user_id=TEST_USER_ID,
                notif_type="weekly_summary",
                title="Weekly Report",
                body="Your summary.",
                channels=["email"],
                db=db,
                user_email="user@example.com",
            )
        mock_email.assert_called_once()

    def test_email_channel_without_user_email_skips_send(self, db):
        with patch("app.email_client.send_email") as mock_email:
            dispatch(
                user_id=TEST_USER_ID,
                notif_type="weekly_summary",
                title="T",
                body="B",
                channels=["email"],
                db=db,
                user_email=None,
            )
        mock_email.assert_not_called()

    def test_email_sent_at_set_on_success(self, db):
        with patch("app.email_client.send_email", return_value=True):
            dispatch(
                user_id=TEST_USER_ID,
                notif_type="weekly_summary",
                title="T",
                body="B",
                channels=["email"],
                db=db,
                user_email="u@example.com",
            )
        n = db.query(Notification).first()
        assert n.sent_at is not None


# ── Multiple channels ─────────────────────────────────────────────────────────

class TestDispatchMultipleChannels:
    def test_push_and_in_app_both_triggered(self, db):
        with patch("app.push_client.send_push", return_value=1) as mock_push:
            dispatch(
                user_id=TEST_USER_ID,
                notif_type="health_alert",
                title="T",
                body="B",
                channels=["push", "in_app"],
                db=db,
            )
        mock_push.assert_called_once()
        n = db.query(Notification).first()
        assert n.sent_at is not None

    def test_returns_id_of_persisted_record(self, db):
        with patch("app.push_client.send_push", return_value=1):
            notif_id = dispatch(
                user_id=TEST_USER_ID,
                notif_type="generic",
                title="T",
                body="B",
                channels=["push", "in_app"],
                db=db,
            )
        n = db.query(Notification).filter_by(id=notif_id).first()
        assert n is not None
