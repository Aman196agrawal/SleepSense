"""Tests for app/push_client.py — FCM/APNs stub behaviour."""
import pytest

from app.push_client import _send_apns, _send_fcm, send_push
from tests.conftest import TEST_USER_ID, make_device_token


# ── _send_fcm stub ────────────────────────────────────────────────────────────

class TestSendFcmStub:
    def test_returns_true_when_no_key(self):
        assert _send_fcm("tok-abc", "Title", "Body", {}) is True

    def test_accepts_payload(self):
        assert _send_fcm("tok-abc", "T", "B", {"screen": "Home"}) is True

    def test_empty_token_still_stubs(self):
        assert _send_fcm("", "T", "B", {}) is True


# ── _send_apns stub ───────────────────────────────────────────────────────────

class TestSendApnsStub:
    def test_returns_true_when_no_key(self):
        assert _send_apns("tok-ios", "Title", "Body", {}) is True

    def test_accepts_payload(self):
        assert _send_apns("tok-ios", "T", "B", {"badge": 1}) is True


# ── send_push (integration with DB tokens) ────────────────────────────────────

class TestSendPush:
    def test_no_tokens_returns_zero(self, db):
        result = send_push(TEST_USER_ID, "T", "B", {}, db)
        assert result == 0

    def test_single_fcm_token_returns_one(self, db):
        make_device_token(db, token="tok-fcm-1", platform="fcm")
        result = send_push(TEST_USER_ID, "T", "B", {}, db)
        assert result == 1

    def test_single_apns_token_returns_one(self, db):
        make_device_token(db, token="tok-apns-1", platform="apns")
        result = send_push(TEST_USER_ID, "T", "B", {}, db)
        assert result == 1

    def test_multiple_tokens_returns_count(self, db):
        make_device_token(db, token="tok-fcm-a", platform="fcm")
        make_device_token(db, token="tok-fcm-b", platform="fcm")
        make_device_token(db, token="tok-apns-a", platform="apns")
        result = send_push(TEST_USER_ID, "T", "B", {}, db)
        assert result == 3

    def test_only_own_tokens_targeted(self, db):
        from tests.conftest import OTHER_USER_ID
        make_device_token(db, user_id=OTHER_USER_ID, token="other-tok", platform="fcm")
        result = send_push(TEST_USER_ID, "T", "B", {}, db)
        assert result == 0

    def test_mixed_platforms(self, db):
        make_device_token(db, token="fcm-mixed", platform="fcm")
        make_device_token(db, token="apns-mixed", platform="apns")
        result = send_push(TEST_USER_ID, "Alert", "Body", {"screen": "Home"}, db)
        assert result == 2

    def test_payload_forwarded(self, db):
        from unittest.mock import patch
        make_device_token(db, token="tok-payload", platform="fcm")
        with patch("app.push_client._send_fcm", return_value=True) as mock_fcm:
            send_push(TEST_USER_ID, "T", "B", {"key": "val"}, db)
        _, _, _, payload_arg = mock_fcm.call_args[0]
        assert payload_arg == {"key": "val"}
