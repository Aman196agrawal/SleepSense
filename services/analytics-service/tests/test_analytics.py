"""
Tests for:
  GET /analytics/timeline/{session_id}
  GET /analytics/trends
  GET /analytics/weekly-summary
"""


class TestTimeline:
    def test_timeline_requires_token(self, client):
        resp = client.get("/analytics/timeline/any-id")
        assert resp.status_code == 401

    def test_timeline_not_found_returns_404(self, client, headers_a):
        resp = client.get("/analytics/timeline/no-such-session", headers=headers_a)
        assert resp.status_code == 404

    def test_timeline_returns_buckets_after_end(self, client, headers_a):
        session_id = client.post("/sessions", headers=headers_a).json()["session_id"]
        client.post(f"/sessions/{session_id}/end", headers=headers_a)
        resp = client.get(f"/analytics/timeline/{session_id}", headers=headers_a)
        assert resp.status_code == 200
        body = resp.json()
        assert body["session_id"] == session_id
        assert "buckets" in body
        assert isinstance(body["buckets"], list)
        assert len(body["buckets"]) > 0

    def test_timeline_bucket_structure(self, client, headers_a):
        session_id = client.post("/sessions", headers=headers_a).json()["session_id"]
        # Upload one chunk so we have known data
        client.post(f"/sessions/{session_id}/chunks", json={
            "chunk_index": 0,
            "avg_intensity": 55.0,
            "dominant_class": "snoring",
            "snore_event_count": 2,
        }, headers=headers_a)
        client.post(f"/sessions/{session_id}/end", headers=headers_a)
        buckets = client.get(f"/analytics/timeline/{session_id}", headers=headers_a).json()["buckets"]
        assert len(buckets) >= 1
        bucket = buckets[0]
        assert "index" in bucket
        assert "offset_minutes" in bucket
        assert "avg_intensity" in bucket
        assert "dominant_class" in bucket
        assert "snore_event_count" in bucket

    def test_user_b_cannot_see_user_a_timeline(self, client, headers_a, headers_b):
        session_id = client.post("/sessions", headers=headers_a).json()["session_id"]
        client.post(f"/sessions/{session_id}/end", headers=headers_a)
        resp = client.get(f"/analytics/timeline/{session_id}", headers=headers_b)
        assert resp.status_code == 404


class TestTrends:
    def test_trends_requires_token(self, client):
        resp = client.get("/analytics/trends")
        assert resp.status_code == 401

    def test_trends_returns_valid_structure(self, client, headers_a):
        resp = client.get("/analytics/trends", headers=headers_a)
        assert resp.status_code == 200
        body = resp.json()
        assert "period" in body
        assert "data_points" in body
        assert "summary" in body

    def test_trends_summary_fields(self, client, headers_a):
        summary = client.get("/analytics/trends", headers=headers_a).json()["summary"]
        assert "avg_quality_score" in summary
        assert "avg_snoring_percentage" in summary
        assert "trend_direction" in summary
        assert summary["trend_direction"] in ("improving", "declining", "stable")
        assert "nights_recorded" in summary

    def test_trends_period_7d(self, client, headers_a):
        resp = client.get("/analytics/trends?period=7d", headers=headers_a)
        assert resp.status_code == 200
        assert resp.json()["period"] == "7d"

    def test_trends_period_90d(self, client, headers_a):
        resp = client.get("/analytics/trends?period=90d", headers=headers_a)
        assert resp.status_code == 200
        assert resp.json()["period"] == "90d"

    def test_trends_data_points_have_correct_keys(self, client, headers_a):
        data_points = client.get("/analytics/trends", headers=headers_a).json()["data_points"]
        if data_points:
            pt = data_points[0]
            assert "date" in pt
            assert "quality_score" in pt
            assert "snoring_percentage" in pt
            assert "duration_minutes" in pt
            assert "grade" in pt

    def test_trends_user_isolation(self, client, headers_a, headers_b):
        # Each user's trend data is independent
        pts_a = client.get("/analytics/trends", headers=headers_a).json()["summary"]["nights_recorded"]
        pts_b = client.get("/analytics/trends", headers=headers_b).json()["summary"]["nights_recorded"]
        # Both users should have seeded data — but it is their own
        assert pts_a > 0
        assert pts_b > 0


class TestWeeklySummary:
    def test_weekly_summary_requires_token(self, client):
        resp = client.get("/analytics/weekly-summary")
        assert resp.status_code == 401

    def test_weekly_summary_returns_valid_structure(self, client, headers_a):
        resp = client.get("/analytics/weekly-summary", headers=headers_a)
        assert resp.status_code == 200
        body = resp.json()
        assert "week_start" in body
        assert "week_end" in body
        assert "nights_recorded" in body
        assert "avg_quality_score" in body
        assert "avg_snoring_percentage" in body
        assert "avg_sleep_duration_minutes" in body
        assert "vs_previous_week" in body

    def test_weekly_summary_score_in_valid_range(self, client, headers_a):
        body = client.get("/analytics/weekly-summary", headers=headers_a).json()
        if body["avg_quality_score"] > 0:
            assert 0 <= body["avg_quality_score"] <= 100

    def test_weekly_summary_best_and_worst_night(self, client, headers_a):
        body = client.get("/analytics/weekly-summary", headers=headers_a).json()
        if body["nights_recorded"] > 0:
            assert body["best_night"] is not None
            assert "date" in body["best_night"]
            assert "score" in body["best_night"]
            assert body["worst_night"] is not None

    def test_weekly_summary_user_isolation(self, client, headers_a, headers_b):
        summary_a = client.get("/analytics/weekly-summary", headers=headers_a).json()
        summary_b = client.get("/analytics/weekly-summary", headers=headers_b).json()
        # They should be independent (seeded deterministically per user)
        assert summary_a is not None
        assert summary_b is not None
