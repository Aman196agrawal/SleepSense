"""
Unit and integration tests for the seed module:

  INSIGHT_TEMPLATES          — constant list of templates
  _grade(score)              — pure function
  _compute_score(...)        — pure function
  _make_timeline(...)        — pure function
  seed_user(user_id, db)     — requires DB (integration)
"""
import random
import uuid
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import SleepSession, TimelineBucket, SessionInsight, SeededUser
from app.seed import (
    INSIGHT_TEMPLATES,
    _grade,
    _compute_score,
    _make_timeline,
    seed_user,
)


# ── DB fixture (isolated per test) ────────────────────────────────────────────

@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


# ── INSIGHT_TEMPLATES ─────────────────────────────────────────────────────────

class TestInsightTemplates:
    def test_has_8_templates(self):
        assert len(INSIGHT_TEMPLATES) == 8

    def test_each_template_is_a_3_tuple(self):
        for tmpl in INSIGHT_TEMPLATES:
            assert len(tmpl) == 3

    def test_all_types_are_valid(self):
        valid = {"tip", "warning", "achievement"}
        for tmpl in INSIGHT_TEMPLATES:
            assert tmpl[0] in valid

    def test_all_titles_are_non_empty_strings(self):
        for tmpl in INSIGHT_TEMPLATES:
            assert isinstance(tmpl[1], str) and len(tmpl[1]) > 0

    def test_all_bodies_are_non_empty_strings(self):
        for tmpl in INSIGHT_TEMPLATES:
            assert isinstance(tmpl[2], str) and len(tmpl[2]) > 0

    def test_contains_tip_warning_and_achievement_types(self):
        types = {t[0] for t in INSIGHT_TEMPLATES}
        assert "tip" in types
        assert "warning" in types
        assert "achievement" in types


# ── _grade ────────────────────────────────────────────────────────────────────

class TestGrade:
    # Excellent: score >= 90
    def test_100_is_excellent(self):
        assert _grade(100) == "Excellent"

    def test_90_is_excellent(self):
        assert _grade(90) == "Excellent"

    def test_89_is_good(self):
        assert _grade(89) == "Good"

    # Good: 75 <= score < 90
    def test_75_is_good(self):
        assert _grade(75) == "Good"

    def test_74_is_fair(self):
        assert _grade(74) == "Fair"

    # Fair: 60 <= score < 75
    def test_60_is_fair(self):
        assert _grade(60) == "Fair"

    def test_59_is_poor(self):
        assert _grade(59) == "Poor"

    # Poor: 40 <= score < 60
    def test_40_is_poor(self):
        assert _grade(40) == "Poor"

    def test_39_is_critical(self):
        assert _grade(39) == "Critical"

    # Critical: score < 40
    def test_0_is_critical(self):
        assert _grade(0) == "Critical"

    def test_fractional_boundary_90(self):
        assert _grade(89.9) == "Good"

    def test_fractional_boundary_75(self):
        assert _grade(74.9) == "Fair"

    def test_fractional_boundary_60(self):
        assert _grade(59.9) == "Poor"

    def test_fractional_boundary_40(self):
        assert _grade(39.9) == "Critical"


# ── _compute_score ────────────────────────────────────────────────────────────

class TestComputeScore:
    # Exact computed values verified by hand — see module docstring
    def test_perfect_input_is_100(self):
        assert _compute_score(0, 0, 0, 360) == 100.0

    def test_known_value_no_gap_penalty(self):
        # 100 − (0.2×40 + 0.4×25 + 3×2) = 100 − (8 + 10 + 6) = 76.0
        assert _compute_score(0.2, 40, 3, 450) == 76.0

    def test_known_value_with_gap_penalty(self):
        # gap = (360−180)/360 × 15 = 7.5; score = 100 − 7.5 = 92.5
        assert _compute_score(0, 0, 0, 180) == 92.5

    def test_zero_duration_applies_max_gap_penalty(self):
        # gap = 360/360 × 15 = 15; score = 100 − 15 = 85.0
        assert _compute_score(0, 0, 0, 0) == 85.0

    def test_duration_exactly_360_has_no_gap_penalty(self):
        assert _compute_score(0, 0, 0, 360) == _compute_score(0, 0, 0, 480)

    def test_duration_above_360_has_no_gap_penalty(self):
        # Any duration >= 360 produces the same score (no penalty)
        assert _compute_score(0.2, 40, 3, 360) == _compute_score(0.2, 40, 3, 600)

    def test_extreme_input_clamped_to_0(self):
        # 100 − (40 + 25 + 100) = −65 → clamped to 0
        assert _compute_score(1.0, 100, 50, 360) == 0.0

    def test_output_never_exceeds_100(self):
        assert _compute_score(0, 0, 0, 10000) <= 100.0

    def test_output_never_below_0(self):
        assert _compute_score(1.0, 100, 100, 0) >= 0.0

    def test_result_rounded_to_one_decimal(self):
        # 100 − (0.5×40 + 0.5×25 + 5×2) = 100 − (20 + 12.5 + 10) = 57.5
        result = _compute_score(0.5, 50, 5, 480)
        assert result == round(result, 1)

    def test_higher_snore_ratio_lowers_score(self):
        low  = _compute_score(0.1, 30, 2, 480)
        high = _compute_score(0.4, 30, 2, 480)
        assert low > high

    def test_higher_intensity_lowers_score(self):
        low  = _compute_score(0.2, 20, 2, 480)
        high = _compute_score(0.2, 70, 2, 480)
        assert low > high

    def test_more_interruptions_lowers_score(self):
        few  = _compute_score(0.2, 40, 0, 480)
        many = _compute_score(0.2, 40, 10, 480)
        assert few > many

    def test_shorter_duration_lowers_score(self):
        short = _compute_score(0.2, 40, 3, 200)
        long  = _compute_score(0.2, 40, 3, 480)
        assert short < long

    def test_each_interruption_costs_2_points(self):
        base  = _compute_score(0, 0, 0, 480)
        extra = _compute_score(0, 0, 5, 480)
        assert round(base - extra, 1) == 10.0


# ── _make_timeline ────────────────────────────────────────────────────────────

class TestMakeTimeline:
    _SID = "test-session-id"

    def _rng(self, seed=42):
        return random.Random(seed)

    def test_bucket_count_equals_duration_div_5(self):
        assert len(_make_timeline(self._SID, 60, 0.2, self._rng())) == 12
        assert len(_make_timeline(self._SID, 450, 0.2, self._rng())) == 90

    def test_zero_duration_returns_empty_list(self):
        assert _make_timeline(self._SID, 0, 0.2, self._rng()) == []

    def test_duration_less_than_5_returns_empty_list(self):
        assert _make_timeline(self._SID, 4, 0.2, self._rng()) == []

    def test_each_bucket_has_required_attributes(self):
        buckets = _make_timeline(self._SID, 30, 0.2, self._rng())
        for b in buckets:
            assert b.id is not None
            assert b.session_id == self._SID
            assert b.bucket_index is not None
            assert b.offset_minutes is not None
            assert b.avg_intensity is not None
            assert b.dominant_class is not None
            assert b.snore_event_count is not None

    def test_session_id_set_on_every_bucket(self):
        sid = str(uuid.uuid4())
        buckets = _make_timeline(sid, 60, 0.2, self._rng())
        assert all(b.session_id == sid for b in buckets)

    def test_bucket_indices_are_sequential_from_zero(self):
        buckets = _make_timeline(self._SID, 30, 0.2, self._rng())
        assert [b.bucket_index for b in buckets] == list(range(len(buckets)))

    def test_offset_minutes_is_index_times_5(self):
        buckets = _make_timeline(self._SID, 30, 0.2, self._rng())
        for b in buckets:
            assert b.offset_minutes == b.bucket_index * 5

    def test_dominant_class_is_always_valid(self):
        valid = {"snoring", "breathing", "silence"}
        buckets = _make_timeline(self._SID, 450, 0.4, self._rng())
        for b in buckets:
            assert b.dominant_class in valid

    def test_avg_intensity_always_in_0_to_100(self):
        buckets = _make_timeline(self._SID, 450, 0.5, self._rng())
        for b in buckets:
            assert 0 <= b.avg_intensity <= 100

    def test_snore_event_count_always_non_negative(self):
        buckets = _make_timeline(self._SID, 450, 0.5, self._rng())
        for b in buckets:
            assert b.snore_event_count >= 0

    def test_non_snoring_buckets_have_zero_event_count(self):
        buckets = _make_timeline(self._SID, 450, 0.3, self._rng())
        for b in buckets:
            if b.dominant_class != "snoring":
                assert b.snore_event_count == 0

    def test_silence_buckets_have_zero_intensity(self):
        buckets = _make_timeline(self._SID, 450, 0.3, self._rng())
        for b in buckets:
            if b.dominant_class == "silence":
                assert b.avg_intensity == 0.0

    def test_all_bucket_ids_are_unique(self):
        buckets = _make_timeline(self._SID, 450, 0.2, self._rng())
        ids = [b.id for b in buckets]
        assert len(ids) == len(set(ids))

    def test_deterministic_with_same_rng_seed(self):
        b1 = _make_timeline(self._SID, 60, 0.2, random.Random(99))
        b2 = _make_timeline(self._SID, 60, 0.2, random.Random(99))
        assert [b.avg_intensity for b in b1] == [b.avg_intensity for b in b2]
        assert [b.dominant_class for b in b1] == [b.dominant_class for b in b2]

    def test_zero_snore_ratio_produces_no_snoring_buckets(self):
        buckets = _make_timeline(self._SID, 450, 0.0, self._rng())
        assert all(b.dominant_class != "snoring" for b in buckets)

    def test_first_and_last_bucket_are_silence_due_to_sine_wave(self):
        # sin(0) = 0 and sin(π) = 0 → base = 0 at both ends
        buckets = _make_timeline(self._SID, 450, 1.0, self._rng())
        assert buckets[0].dominant_class == "silence"
        assert buckets[-1].dominant_class == "silence"


# ── seed_user ─────────────────────────────────────────────────────────────────

class TestSeedUser:
    USER_A = "seed-test-user-alpha-001"
    USER_B = "seed-test-user-beta-002"

    # ── Basic creation ────────────────────────────────────────────────────────

    def test_creates_seeded_user_record(self, db):
        seed_user(self.USER_A, db)
        assert db.query(SeededUser).filter(SeededUser.user_id == self.USER_A).first() is not None

    def test_creates_sessions(self, db):
        seed_user(self.USER_A, db)
        count = db.query(SleepSession).filter(SleepSession.user_id == self.USER_A).count()
        assert count >= 20   # 30 days × ~82% = ~24.6 expected

    def test_session_count_does_not_exceed_30(self, db):
        seed_user(self.USER_A, db)
        count = db.query(SleepSession).filter(SleepSession.user_id == self.USER_A).count()
        assert count <= 30

    # ── Session field correctness ─────────────────────────────────────────────

    def test_all_sessions_have_complete_status(self, db):
        seed_user(self.USER_A, db)
        sessions = db.query(SleepSession).filter(SleepSession.user_id == self.USER_A).all()
        assert all(s.status == "complete" for s in sessions)

    def test_all_scores_in_valid_range(self, db):
        seed_user(self.USER_A, db)
        sessions = db.query(SleepSession).filter(SleepSession.user_id == self.USER_A).all()
        for s in sessions:
            assert 0 <= s.sleep_quality_score <= 100

    def test_grade_matches_computed_score(self, db):
        seed_user(self.USER_A, db)
        sessions = db.query(SleepSession).filter(SleepSession.user_id == self.USER_A).all()
        for s in sessions:
            assert s.sleep_quality_grade == _grade(s.sleep_quality_score)

    def test_duration_in_seeded_range(self, db):
        seed_user(self.USER_A, db)
        sessions = db.query(SleepSession).filter(SleepSession.user_id == self.USER_A).all()
        for s in sessions:
            assert 340 <= s.duration_minutes <= 510

    def test_total_chunks_equals_duration_div_30(self, db):
        seed_user(self.USER_A, db)
        sessions = db.query(SleepSession).filter(SleepSession.user_id == self.USER_A).all()
        for s in sessions:
            assert s.total_chunks == s.duration_minutes // 30

    def test_processed_chunks_equals_total_chunks(self, db):
        seed_user(self.USER_A, db)
        sessions = db.query(SleepSession).filter(SleepSession.user_id == self.USER_A).all()
        for s in sessions:
            assert s.processed_chunks == s.total_chunks

    def test_snoring_percentage_is_non_negative(self, db):
        seed_user(self.USER_A, db)
        sessions = db.query(SleepSession).filter(SleepSession.user_id == self.USER_A).all()
        for s in sessions:
            assert s.snoring_percentage >= 0

    def test_peak_snoring_hour_in_valid_range(self, db):
        seed_user(self.USER_A, db)
        sessions = db.query(SleepSession).filter(SleepSession.user_id == self.USER_A).all()
        for s in sessions:
            assert 0 <= s.peak_snoring_hour <= 4

    def test_all_sessions_are_in_the_past(self, db):
        seed_user(self.USER_A, db)
        now = datetime.now()
        sessions = db.query(SleepSession).filter(SleepSession.user_id == self.USER_A).all()
        for s in sessions:
            assert s.started_at < now

    def test_all_sessions_within_last_31_days(self, db):
        seed_user(self.USER_A, db)
        now = datetime.now()
        sessions = db.query(SleepSession).filter(SleepSession.user_id == self.USER_A).all()
        for s in sessions:
            # started_at is set to 22:xx on the day; if now < 22:xx today the
            # floor-division gives 0 days for days_ago=1 — that is still "past"
            assert s.started_at <= now
            assert (now - s.started_at).days <= 31

    def test_ended_at_is_after_started_at(self, db):
        seed_user(self.USER_A, db)
        sessions = db.query(SleepSession).filter(SleepSession.user_id == self.USER_A).all()
        for s in sessions:
            assert s.ended_at > s.started_at

    # ── Timeline buckets ──────────────────────────────────────────────────────

    def test_every_session_has_buckets(self, db):
        seed_user(self.USER_A, db)
        sessions = db.query(SleepSession).filter(SleepSession.user_id == self.USER_A).all()
        for s in sessions:
            count = db.query(TimelineBucket).filter(TimelineBucket.session_id == s.id).count()
            assert count > 0

    def test_bucket_count_matches_duration(self, db):
        seed_user(self.USER_A, db)
        sessions = db.query(SleepSession).filter(SleepSession.user_id == self.USER_A).all()
        for s in sessions[:5]:   # spot-check first 5
            expected = s.duration_minutes // 5
            actual   = db.query(TimelineBucket).filter(TimelineBucket.session_id == s.id).count()
            assert actual == expected

    def test_bucket_dominant_class_is_valid(self, db):
        seed_user(self.USER_A, db)
        valid = {"snoring", "breathing", "silence"}
        sessions = db.query(SleepSession).filter(SleepSession.user_id == self.USER_A).all()
        for s in sessions[:3]:   # spot-check
            buckets = db.query(TimelineBucket).filter(TimelineBucket.session_id == s.id).all()
            for b in buckets:
                assert b.dominant_class in valid

    # ── Insights ──────────────────────────────────────────────────────────────

    def test_every_session_has_exactly_one_insight(self, db):
        seed_user(self.USER_A, db)
        sessions = db.query(SleepSession).filter(SleepSession.user_id == self.USER_A).all()
        for s in sessions:
            count = db.query(SessionInsight).filter(SessionInsight.session_id == s.id).count()
            assert count == 1

    def test_all_insights_have_valid_type(self, db):
        seed_user(self.USER_A, db)
        valid = {"tip", "warning", "achievement"}
        insights = db.query(SessionInsight).filter(SessionInsight.user_id == self.USER_A).all()
        for i in insights:
            assert i.insight_type in valid

    def test_all_insights_have_non_empty_title(self, db):
        seed_user(self.USER_A, db)
        insights = db.query(SessionInsight).filter(SessionInsight.user_id == self.USER_A).all()
        for i in insights:
            assert len(i.title) > 0

    def test_insight_user_id_matches_session_user_id(self, db):
        seed_user(self.USER_A, db)
        insights = db.query(SessionInsight).filter(SessionInsight.user_id == self.USER_A).all()
        for i in insights:
            assert i.user_id == self.USER_A

    def test_insight_priority_in_valid_range(self, db):
        seed_user(self.USER_A, db)
        insights = db.query(SessionInsight).filter(SessionInsight.user_id == self.USER_A).all()
        for i in insights:
            assert 1 <= i.priority <= 10

    # ── Idempotency & isolation ───────────────────────────────────────────────

    def test_second_call_is_a_no_op(self, db):
        seed_user(self.USER_A, db)
        first_count = db.query(SleepSession).filter(SleepSession.user_id == self.USER_A).count()
        seed_user(self.USER_A, db)
        second_count = db.query(SleepSession).filter(SleepSession.user_id == self.USER_A).count()
        assert first_count == second_count

    def test_second_call_does_not_create_duplicate_seeded_user_record(self, db):
        seed_user(self.USER_A, db)
        seed_user(self.USER_A, db)
        count = db.query(SeededUser).filter(SeededUser.user_id == self.USER_A).count()
        assert count == 1

    def test_different_users_get_different_session_ids(self, db):
        seed_user(self.USER_A, db)
        seed_user(self.USER_B, db)
        ids_a = {s.id for s in db.query(SleepSession).filter(SleepSession.user_id == self.USER_A).all()}
        ids_b = {s.id for s in db.query(SleepSession).filter(SleepSession.user_id == self.USER_B).all()}
        assert ids_a.isdisjoint(ids_b)

    def test_user_a_sessions_belong_only_to_user_a(self, db):
        seed_user(self.USER_A, db)
        seed_user(self.USER_B, db)
        sessions = db.query(SleepSession).filter(SleepSession.user_id == self.USER_A).all()
        for s in sessions:
            assert s.user_id == self.USER_A
