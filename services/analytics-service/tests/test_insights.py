"""
Tests for:
  GET    /insights
  PATCH  /insights/{id}/read
"""


class TestGetInsights:
    def test_insights_requires_token(self, client):
        resp = client.get("/insights")
        assert resp.status_code == 401

    def test_insights_returns_list(self, client, headers_a):
        resp = client.get("/insights", headers=headers_a)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_insights_returns_at_least_one(self, client, headers_a):
        insights = client.get("/insights", headers=headers_a).json()
        assert len(insights) >= 1

    def test_insights_default_limit_is_10(self, client, headers_a):
        insights = client.get("/insights", headers=headers_a).json()
        assert len(insights) <= 10

    def test_insights_custom_limit(self, client, headers_a):
        insights = client.get("/insights?limit=3", headers=headers_a).json()
        assert len(insights) <= 3

    def test_each_insight_has_required_fields(self, client, headers_a):
        insights = client.get("/insights", headers=headers_a).json()
        required = {"id", "title", "body", "insight_type", "priority", "is_read"}
        for insight in insights:
            assert required.issubset(insight.keys()), (
                f"Insight missing fields: {required - insight.keys()}"
            )

    def test_insight_type_is_valid(self, client, headers_a):
        valid_types = {"tip", "warning", "achievement", "pattern", "goal"}
        insights = client.get("/insights", headers=headers_a).json()
        for insight in insights:
            assert insight["insight_type"] in valid_types, (
                f"Unknown insight_type: {insight['insight_type']}"
            )

    def test_insights_user_isolation(self, client, headers_a, headers_b):
        insights_a = client.get("/insights", headers=headers_a).json()
        insights_b = client.get("/insights", headers=headers_b).json()
        # Session-based insight IDs (uuid) should not overlap
        ids_a = {i["id"] for i in insights_a if i.get("session_id")}
        ids_b = {i["id"] for i in insights_b if i.get("session_id")}
        assert ids_a.isdisjoint(ids_b), "Insight IDs leaked across users"

    def test_insights_generated_after_session_end(self, client, headers_a):
        # End a real session → should generate a session insight
        session_id = client.post("/sessions", headers=headers_a).json()["session_id"]
        client.post(f"/sessions/{session_id}/end", headers=headers_a)
        insights = client.get("/insights", headers=headers_a).json()
        session_insights = [i for i in insights if i.get("session_id") == session_id]
        assert len(session_insights) >= 1


class TestMarkInsightRead:
    def test_mark_read_returns_is_read_true(self, client, headers_a):
        # End a session to produce a stored insight
        session_id = client.post("/sessions", headers=headers_a).json()["session_id"]
        client.post(f"/sessions/{session_id}/end", headers=headers_a)

        insights = client.get("/insights", headers=headers_a).json()
        stored = [i for i in insights if i.get("session_id") == session_id]
        assert stored, "No stored insight found to mark as read"

        insight_id = stored[0]["id"]
        resp = client.patch(f"/insights/{insight_id}/read", headers=headers_a)
        assert resp.status_code == 200
        assert resp.json()["is_read"] is True

    def test_mark_nonexistent_insight_still_returns_200(self, client, headers_a):
        # Mark-as-read is idempotent — unknown IDs should not crash
        resp = client.patch("/insights/nonexistent-id/read", headers=headers_a)
        assert resp.status_code == 200

    def test_mark_read_requires_token(self, client):
        resp = client.patch("/insights/some-id/read")
        assert resp.status_code == 401
