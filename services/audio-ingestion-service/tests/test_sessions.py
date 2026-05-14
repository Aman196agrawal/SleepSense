"""
Tests for Audio Ingestion Service:
  POST   /sessions                        — start session
  POST   /sessions/{id}/chunks            — upload audio chunk
  POST   /sessions/{id}/end               — end session
  GET    /sessions/{id}/status            — session status polling
"""
from io import BytesIO
from tests.conftest import _upload, _fake_audio


# ── POST /sessions ─────────────────────────────────────────────────────────────

class TestStartSession:
    def test_returns_201(self, client, auth_headers):
        assert client.post("/sessions", headers=auth_headers).status_code == 201

    def test_returns_session_id(self, client, auth_headers):
        body = client.post("/sessions", headers=auth_headers).json()
        assert "session_id" in body
        assert len(body["session_id"]) == 36  # UUID format

    def test_returns_upload_token(self, client, auth_headers):
        body = client.post("/sessions", headers=auth_headers).json()
        assert "upload_token" in body
        assert len(body["upload_token"]) > 10

    def test_status_is_recording(self, client, auth_headers):
        body = client.post("/sessions", headers=auth_headers).json()
        assert body["status"] == "recording"

    def test_returns_started_at(self, client, auth_headers):
        body = client.post("/sessions", headers=auth_headers).json()
        assert "started_at" in body

    def test_requires_auth(self, client):
        assert client.post("/sessions").status_code in (401, 403)

    def test_second_active_session_returns_409(self, client, auth_headers):
        client.post("/sessions", headers=auth_headers)
        resp = client.post("/sessions", headers=auth_headers)
        assert resp.status_code == 409

    def test_second_session_allowed_after_end(self, client, auth_headers, active_session):
        client.post(f"/sessions/{active_session}/end", json={}, headers=auth_headers)
        resp = client.post("/sessions", headers=auth_headers)
        assert resp.status_code == 201

    def test_different_users_can_have_concurrent_sessions(self, client, auth_headers, other_auth_headers):
        assert client.post("/sessions", headers=auth_headers).status_code == 201
        assert client.post("/sessions", headers=other_auth_headers).status_code == 201


# ── POST /sessions/{id}/chunks ─────────────────────────────────────────────────

class TestUploadChunk:
    def test_returns_202(self, client, auth_headers, active_session):
        resp = _upload(client, active_session, auth_headers)
        assert resp.status_code == 202

    def test_returns_chunk_id(self, client, auth_headers, active_session):
        body = _upload(client, active_session, auth_headers).json()
        assert "chunk_id" in body
        assert len(body["chunk_id"]) == 36

    def test_returns_queued_status(self, client, auth_headers, active_session):
        body = _upload(client, active_session, auth_headers).json()
        assert body["status"] == "queued"

    def test_returns_chunk_index(self, client, auth_headers, active_session):
        body = _upload(client, active_session, auth_headers).json()
        assert body["chunk_index"] == 0

    def test_requires_auth(self, client, active_session):
        from io import BytesIO
        resp = client.post(
            f"/sessions/{active_session}/chunks",
            files={"audio": ("c.opus", BytesIO(b"\x00" * 512), "audio/opus")},
            data={"chunk_index": "0", "duration_seconds": "30"},
        )
        assert resp.status_code in (401, 403)

    def test_invalid_session_returns_404(self, client, auth_headers):
        resp = _upload(client, "non-existent-session-id", auth_headers)
        assert resp.status_code == 404

    def test_wrong_user_session_returns_404(self, client, other_auth_headers, active_session):
        resp = _upload(client, active_session, other_auth_headers)
        assert resp.status_code == 404

    def test_first_chunk_must_be_index_zero(self, client, auth_headers, active_session):
        resp = _upload(client, active_session, auth_headers, chunk_index=1)
        assert resp.status_code == 422

    def test_sequential_index_enforced(self, client, auth_headers, active_session):
        _upload(client, active_session, auth_headers, chunk_index=0)
        resp = _upload(client, active_session, auth_headers, chunk_index=2)  # skips 1
        assert resp.status_code == 422

    def test_second_chunk_accepted_after_first(self, client, auth_headers, active_session):
        _upload(client, active_session, auth_headers, chunk_index=0)
        resp = _upload(client, active_session, auth_headers, chunk_index=1)
        assert resp.status_code == 202

    def test_invalid_mime_type_returns_400(self, client, auth_headers, active_session):
        resp = client.post(
            f"/sessions/{active_session}/chunks",
            files={"audio": ("c.mp3", BytesIO(b"\x00" * 512), "video/mp4")},
            data={"chunk_index": "0", "duration_seconds": "30"},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_file_too_large_returns_413(self, client, auth_headers, active_session):
        oversized = _fake_audio(11 * 1024 * 1024)  # 11 MB
        resp = client.post(
            f"/sessions/{active_session}/chunks",
            files={"audio": ("big.opus", BytesIO(oversized), "audio/opus")},
            data={"chunk_index": "0", "duration_seconds": "30"},
            headers=auth_headers,
        )
        assert resp.status_code == 413

    def test_chunk_increments_total_chunks(self, client, auth_headers, active_session):
        _upload(client, active_session, auth_headers, chunk_index=0)
        _upload(client, active_session, auth_headers, chunk_index=1)
        status = client.get(f"/sessions/{active_session}/status", headers=auth_headers).json()
        assert status["total_chunks"] == 2

    def test_upload_to_ended_session_returns_404(self, client, auth_headers, active_session):
        client.post(f"/sessions/{active_session}/end", json={}, headers=auth_headers)
        resp = _upload(client, active_session, auth_headers, chunk_index=0)
        assert resp.status_code == 404

    def test_rate_limit_resets_between_tests(self, client, auth_headers, active_session):
        # Verify rate limiter is cleared between tests
        resp = _upload(client, active_session, auth_headers, chunk_index=0)
        assert resp.status_code == 202


# ── POST /sessions/{id}/end ────────────────────────────────────────────────────

class TestEndSession:
    def test_returns_200(self, client, auth_headers, active_session):
        resp = client.post(f"/sessions/{active_session}/end", json={}, headers=auth_headers)
        assert resp.status_code == 200

    def test_status_becomes_processing(self, client, auth_headers, active_session):
        body = client.post(f"/sessions/{active_session}/end", json={}, headers=auth_headers).json()
        assert body["status"] == "processing"

    def test_returns_session_id(self, client, auth_headers, active_session):
        body = client.post(f"/sessions/{active_session}/end", json={}, headers=auth_headers).json()
        assert body["session_id"] == active_session

    def test_returns_estimated_ready_time(self, client, auth_headers, active_session):
        body = client.post(f"/sessions/{active_session}/end", json={}, headers=auth_headers).json()
        assert "estimated_ready_in_seconds" in body
        assert body["estimated_ready_in_seconds"] > 0

    def test_accepts_ended_at_timestamp(self, client, auth_headers, active_session):
        resp = client.post(
            f"/sessions/{active_session}/end",
            json={"ended_at": "2026-05-13T07:30:00"},
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_accepts_notes(self, client, auth_headers, active_session):
        resp = client.post(
            f"/sessions/{active_session}/end",
            json={"notes": "Slept well tonight"},
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_accepts_room_temperature(self, client, auth_headers, active_session):
        resp = client.post(
            f"/sessions/{active_session}/end",
            json={"room_temperature": 22.5},
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_invalid_session_returns_404(self, client, auth_headers):
        resp = client.post("/sessions/no-such-session/end", json={}, headers=auth_headers)
        assert resp.status_code == 404

    def test_wrong_user_returns_404(self, client, other_auth_headers, active_session):
        resp = client.post(f"/sessions/{active_session}/end", json={}, headers=other_auth_headers)
        assert resp.status_code == 404

    def test_requires_auth(self, client, active_session):
        resp = client.post(f"/sessions/{active_session}/end", json={})
        assert resp.status_code in (401, 403)

    def test_ending_already_ended_session_returns_409(self, client, auth_headers, active_session):
        client.post(f"/sessions/{active_session}/end", json={}, headers=auth_headers)
        resp = client.post(f"/sessions/{active_session}/end", json={}, headers=auth_headers)
        assert resp.status_code == 409

    def test_status_endpoint_reflects_processing_after_end(self, client, auth_headers, active_session):
        client.post(f"/sessions/{active_session}/end", json={}, headers=auth_headers)
        status = client.get(f"/sessions/{active_session}/status", headers=auth_headers).json()
        assert status["status"] == "processing"


# ── GET /sessions/{id}/status ──────────────────────────────────────────────────

class TestSessionStatus:
    def test_returns_200(self, client, auth_headers, active_session):
        assert client.get(f"/sessions/{active_session}/status", headers=auth_headers).status_code == 200

    def test_has_required_fields(self, client, auth_headers, active_session):
        body = client.get(f"/sessions/{active_session}/status", headers=auth_headers).json()
        for field in ("status", "processed_chunks", "total_chunks", "percent_complete"):
            assert field in body

    def test_status_is_recording_before_end(self, client, auth_headers, active_session):
        body = client.get(f"/sessions/{active_session}/status", headers=auth_headers).json()
        assert body["status"] == "recording"

    def test_total_chunks_reflects_uploads(self, client, auth_headers, active_session):
        _upload(client, active_session, auth_headers, chunk_index=0)
        _upload(client, active_session, auth_headers, chunk_index=1)
        _upload(client, active_session, auth_headers, chunk_index=2)
        body = client.get(f"/sessions/{active_session}/status", headers=auth_headers).json()
        assert body["total_chunks"] == 3

    def test_percent_complete_zero_when_no_chunks_done(self, client, auth_headers, active_session):
        _upload(client, active_session, auth_headers, chunk_index=0)
        body = client.get(f"/sessions/{active_session}/status", headers=auth_headers).json()
        assert body["percent_complete"] == 0.0

    def test_invalid_session_returns_404(self, client, auth_headers):
        resp = client.get("/sessions/ghost-session/status", headers=auth_headers)
        assert resp.status_code == 404

    def test_requires_auth(self, client, active_session):
        resp = client.get(f"/sessions/{active_session}/status")
        assert resp.status_code in (401, 403)

    def test_wrong_user_returns_404(self, client, other_auth_headers, active_session):
        resp = client.get(f"/sessions/{active_session}/status", headers=other_auth_headers)
        assert resp.status_code == 404
