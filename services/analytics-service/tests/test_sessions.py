"""
Tests for the session lifecycle:
  POST   /sessions            — start
  POST   /sessions/{id}/end   — end
  POST   /sessions/{id}/chunks — upload chunk
  GET    /sessions            — list
  GET    /sessions/{id}       — detail
"""
import time


class TestListSessions:
    def test_list_sessions_requires_token(self, client):
        resp = client.get("/sessions")
        assert resp.status_code == 401

    def test_list_sessions_returns_seeded_data(self, client, headers_a):
        resp = client.get("/sessions", headers=headers_a)
        assert resp.status_code == 200
        sessions = resp.json()
        # Seed produces 30 days of data
        assert len(sessions) >= 20

    def test_list_sessions_only_returns_own_sessions(self, client, headers_a, headers_b):
        # Both users get their own seeded data — sessions must not bleed across users
        sessions_a = client.get("/sessions", headers=headers_a).json()
        sessions_b = client.get("/sessions", headers=headers_b).json()
        ids_a = {s["id"] for s in sessions_a}
        ids_b = {s["id"] for s in sessions_b}
        assert ids_a.isdisjoint(ids_b), "User A and User B share session IDs — isolation broken"

    def test_list_sessions_default_limit_is_20(self, client, headers_a):
        resp = client.get("/sessions", headers=headers_a)
        assert len(resp.json()) <= 20

    def test_list_sessions_custom_limit(self, client, headers_a):
        resp = client.get("/sessions?limit=5", headers=headers_a)
        assert len(resp.json()) <= 5

    def test_list_sessions_all_have_complete_status(self, client, headers_a):
        sessions = client.get("/sessions", headers=headers_a).json()
        for s in sessions:
            assert s["status"] == "complete"


class TestStartSession:
    def test_start_session_requires_token(self, client):
        resp = client.post("/sessions")
        assert resp.status_code == 401

    def test_start_session_returns_session_id_and_status(self, client, headers_a):
        resp = client.post("/sessions", headers=headers_a)
        assert resp.status_code == 201
        body = resp.json()
        assert "session_id" in body
        assert body["status"] == "recording"
        assert "started_at" in body

    def test_start_session_creates_unique_ids(self, client, headers_a):
        id1 = client.post("/sessions", headers=headers_a).json()["session_id"]
        id2 = client.post("/sessions", headers=headers_a).json()["session_id"]
        assert id1 != id2


class TestEndSession:
    def test_end_session_returns_complete_stats(self, client, headers_a):
        session_id = client.post("/sessions", headers=headers_a).json()["session_id"]
        resp = client.post(f"/sessions/{session_id}/end", headers=headers_a)
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "complete"
        assert body["sleep_quality_score"] is not None
        assert body["sleep_quality_grade"] in ("Excellent", "Good", "Fair", "Poor")
        assert body["snoring_percentage"] is not None
        assert body["duration_minutes"] >= 1

    def test_end_session_score_is_in_valid_range(self, client, headers_a):
        session_id = client.post("/sessions", headers=headers_a).json()["session_id"]
        body = client.post(f"/sessions/{session_id}/end", headers=headers_a).json()
        assert 0 <= body["sleep_quality_score"] <= 100

    def test_end_session_not_found_returns_404(self, client, headers_a):
        resp = client.post("/sessions/non-existent-id/end", headers=headers_a)
        assert resp.status_code == 404

    def test_end_session_requires_token(self, client, headers_a):
        session_id = client.post("/sessions", headers=headers_a).json()["session_id"]
        resp = client.post(f"/sessions/{session_id}/end")
        assert resp.status_code == 401

    def test_user_b_cannot_end_user_a_session(self, client, headers_a, headers_b):
        session_id = client.post("/sessions", headers=headers_a).json()["session_id"]
        resp = client.post(f"/sessions/{session_id}/end", headers=headers_b)
        assert resp.status_code == 404

    def test_ended_session_appears_in_list(self, client, headers_a):
        session_id = client.post("/sessions", headers=headers_a).json()["session_id"]
        client.post(f"/sessions/{session_id}/end", headers=headers_a)
        sessions = client.get("/sessions", headers=headers_a).json()
        ids = [s["id"] for s in sessions]
        assert session_id in ids


class TestGetSession:
    def test_get_session_detail(self, client, headers_a):
        session_id = client.post("/sessions", headers=headers_a).json()["session_id"]
        client.post(f"/sessions/{session_id}/end", headers=headers_a)
        resp = client.get(f"/sessions/{session_id}", headers=headers_a)
        assert resp.status_code == 200
        assert resp.json()["id"] == session_id

    def test_get_session_not_found_returns_404(self, client, headers_a):
        resp = client.get("/sessions/no-such-id", headers=headers_a)
        assert resp.status_code == 404

    def test_user_b_cannot_read_user_a_session(self, client, headers_a, headers_b):
        session_id = client.post("/sessions", headers=headers_a).json()["session_id"]
        resp = client.get(f"/sessions/{session_id}", headers=headers_b)
        assert resp.status_code == 404


class TestChunkUpload:
    CHUNK = {
        "chunk_index": 0,
        "avg_intensity": 45.0,
        "dominant_class": "snoring",
        "snore_event_count": 3,
    }

    def test_upload_chunk_returns_ok(self, client, headers_a):
        session_id = client.post("/sessions", headers=headers_a).json()["session_id"]
        resp = client.post(f"/sessions/{session_id}/chunks", json=self.CHUNK, headers=headers_a)
        assert resp.status_code == 201
        assert resp.json()["status"] == "ok"
        assert resp.json()["chunk_index"] == 0

    def test_upload_chunk_to_nonexistent_session_returns_404(self, client, headers_a):
        resp = client.post("/sessions/no-such-id/chunks", json=self.CHUNK, headers=headers_a)
        assert resp.status_code == 404

    def test_upload_chunk_requires_token(self, client, headers_a):
        session_id = client.post("/sessions", headers=headers_a).json()["session_id"]
        resp = client.post(f"/sessions/{session_id}/chunks", json=self.CHUNK)
        assert resp.status_code == 401

    def test_chunk_data_used_in_session_score(self, client, headers_a):
        session_id = client.post("/sessions", headers=headers_a).json()["session_id"]
        # Upload several silence chunks → expect better score
        for i in range(5):
            client.post(f"/sessions/{session_id}/chunks", json={
                "chunk_index": i,
                "avg_intensity": 5.0,
                "dominant_class": "silence",
                "snore_event_count": 0,
            }, headers=headers_a)
        body = client.post(f"/sessions/{session_id}/end", headers=headers_a).json()
        assert body["snoring_percentage"] == 0.0
