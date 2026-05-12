"""
Unit tests for patterns.generate_pattern_insights().

Pure unit tests — no HTTP client, no database.  SQLAlchemy model objects are
constructed in memory and passed straight into the function, so each test is
fast and deterministic.

Rules under test (in order):
  1. Consecutive bad nights       (streak of score < 60 nights)
  2. Week-over-week trend         (7-session rolling comparison)
  3. Peak snoring time pattern    (same peak_snoring_hour in 3+ of last 5)
  4. Short sleep duration         (3+ of last 5 sessions < 6 h)
  5. Recording streak             (7+ consecutive calendar days)
  6. Best day-of-week pattern     (14+ sessions, best/worst day diff >= 10)
  7. Lifestyle correlations       (alcohol / exercise / stress vs. sleep score)
"""
import uuid
from datetime import datetime, date, timedelta, time

from app.patterns import generate_pattern_insights
from app.models import SleepSession, LifestyleLog


# ── Builders ──────────────────────────────────────────────────────────────────

def _session(
    *,
    score: float = 75.0,
    days_ago: int = 0,
    duration: int = 450,
    peak_hour: int | None = 2,
) -> SleepSession:
    started = datetime.combine(
        date.today() - timedelta(days=days_ago), time(22, 0)
    )
    return SleepSession(
        id=str(uuid.uuid4()),
        user_id="u1",
        started_at=started,
        ended_at=started + timedelta(minutes=duration),
        duration_minutes=duration,
        status="complete",
        sleep_quality_score=score,
        sleep_quality_grade="Good",
        peak_snoring_hour=peak_hour,
        snoring_percentage=20.0,
    )


def _log(
    *,
    days_ago: int = 0,
    alcohol_units: float = 0.0,
    exercise_minutes: int = 0,
    stress_level: int = 3,
) -> LifestyleLog:
    return LifestyleLog(
        id=str(uuid.uuid4()),
        user_id="u1",
        logged_date=(date.today() - timedelta(days=days_ago)).isoformat(),
        alcohol_units=alcohol_units,
        exercise_minutes=exercise_minutes,
        stress_level=stress_level,
        caffeine_cups=0,
        sleep_aid_used=False,
    )


def _newest_first(*sessions) -> list:
    """Sort sessions newest-first, as the caller contract expects."""
    return sorted(sessions, key=lambda s: s.started_at, reverse=True)


# ── Empty / trivial ───────────────────────────────────────────────────────────

class TestEmptyInputs:
    def test_empty_sessions_returns_empty_list(self):
        assert generate_pattern_insights("u1", [], []) == []

    def test_result_is_always_a_list(self):
        assert isinstance(generate_pattern_insights("u1", [], []), list)

    def test_sessions_with_no_lifestyle_logs_still_works(self):
        sessions = _newest_first(*[_session(score=50, days_ago=i) for i in range(3)])
        result = generate_pattern_insights("u1", sessions, [])
        assert isinstance(result, list)
        assert len(result) >= 1


# ── Rule 1: Consecutive bad nights ───────────────────────────────────────────

class TestConsecutiveBadNights:
    def test_three_bad_nights_triggers_warning(self):
        sessions = _newest_first(*[_session(score=50, days_ago=i) for i in range(3)])
        result = generate_pattern_insights("u1", sessions, [])
        streak_warnings = [i for i in result if "consecutive" in i["title"]]
        assert streak_warnings != []

    def test_warning_title_contains_streak_count(self):
        sessions = _newest_first(*[_session(score=50, days_ago=i) for i in range(3)])
        result = generate_pattern_insights("u1", sessions, [])
        warnings = [i for i in result if "consecutive" in i["title"]]
        assert "3" in warnings[0]["title"]

    def test_five_bad_nights_title_shows_five(self):
        sessions = _newest_first(*[_session(score=50, days_ago=i) for i in range(5)])
        result = generate_pattern_insights("u1", sessions, [])
        warnings = [i for i in result if "consecutive" in i["title"]]
        assert "5" in warnings[0]["title"]

    def test_streak_type_is_warning(self):
        sessions = _newest_first(*[_session(score=50, days_ago=i) for i in range(3)])
        result = generate_pattern_insights("u1", sessions, [])
        warnings = [i for i in result if "consecutive" in i["title"]]
        assert warnings[0]["type"] == "warning"

    def test_two_bad_nights_does_not_trigger(self):
        sessions = _newest_first(*[_session(score=50, days_ago=i) for i in range(2)])
        result = generate_pattern_insights("u1", sessions, [])
        assert [i for i in result if "consecutive" in i["title"]] == []

    def test_good_night_breaks_streak(self):
        sessions = _newest_first(
            _session(score=50, days_ago=0),
            _session(score=50, days_ago=1),
            _session(score=80, days_ago=2),   # good night — breaks streak
            _session(score=50, days_ago=3),
            _session(score=50, days_ago=4),
        )
        result = generate_pattern_insights("u1", sessions, [])
        assert [i for i in result if "consecutive" in i["title"]] == []

    def test_score_exactly_60_does_not_count_as_bad(self):
        # Rule is score < 60; 60 breaks the streak
        sessions = _newest_first(
            _session(score=50, days_ago=0),
            _session(score=50, days_ago=1),
            _session(score=60, days_ago=2),   # boundary — not bad
        )
        result = generate_pattern_insights("u1", sessions, [])
        assert [i for i in result if "consecutive" in i["title"]] == []

    def test_score_59_counts_as_bad(self):
        sessions = _newest_first(*[_session(score=59, days_ago=i) for i in range(3)])
        result = generate_pattern_insights("u1", sessions, [])
        assert [i for i in result if "consecutive" in i["title"]] != []

    def test_only_one_streak_insight_generated(self):
        sessions = _newest_first(*[_session(score=50, days_ago=i) for i in range(10)])
        result = generate_pattern_insights("u1", sessions, [])
        assert len([i for i in result if "consecutive" in i["title"]]) == 1


# ── Rule 2: Week-over-week trend ─────────────────────────────────────────────

class TestWeekOverWeekTrend:
    def test_fewer_than_7_sessions_no_trend(self):
        sessions = _newest_first(*[_session(score=80, days_ago=i) for i in range(6)])
        result = generate_pattern_insights("u1", sessions, [])
        trend = [i for i in result if "improving" in i["title"] or "declining" in i["title"]]
        assert trend == []

    def test_exactly_7_sessions_no_trend(self):
        # With 7 sessions scores[7:] is empty → old_avg defaults to new_avg → change = 0
        sessions = _newest_first(*[_session(score=80, days_ago=i) for i in range(7)])
        result = generate_pattern_insights("u1", sessions, [])
        trend = [i for i in result if "improving" in i["title"] or "declining" in i["title"]]
        assert trend == []

    def test_improving_trend_triggers_achievement(self):
        sessions = _newest_first(
            *[_session(score=85, days_ago=i)   for i in range(7)],   # recent 7, avg 85
            *[_session(score=75, days_ago=7+i) for i in range(7)],   # older 7,  avg 75
        )
        result = generate_pattern_insights("u1", sessions, [])
        improvements = [i for i in result if "improving" in i["title"]]
        assert improvements != []
        assert improvements[0]["type"] == "achievement"

    def test_declining_trend_triggers_warning(self):
        sessions = _newest_first(
            *[_session(score=65, days_ago=i)   for i in range(7)],   # recent 7, avg 65
            *[_session(score=80, days_ago=7+i) for i in range(7)],   # older 7,  avg 80
        )
        result = generate_pattern_insights("u1", sessions, [])
        declines = [i for i in result if "declining" in i["title"]]
        assert declines != []
        assert declines[0]["type"] == "warning"

    def test_stable_trend_no_insight(self):
        sessions = _newest_first(*[_session(score=75, days_ago=i) for i in range(14)])
        result = generate_pattern_insights("u1", sessions, [])
        trend = [i for i in result if "improving" in i["title"] or "declining" in i["title"]]
        assert trend == []

    def test_change_of_4_points_is_stable(self):
        # Threshold is 5 pts; a change of 4 should not trigger
        sessions = _newest_first(
            *[_session(score=79, days_ago=i)   for i in range(7)],
            *[_session(score=75, days_ago=7+i) for i in range(7)],
        )
        result = generate_pattern_insights("u1", sessions, [])
        trend = [i for i in result if "improving" in i["title"] or "declining" in i["title"]]
        assert trend == []


# ── Rule 3: Peak snoring time pattern ────────────────────────────────────────

class TestPeakSnoringPattern:
    def test_same_hour_3_of_5_nights_triggers_tip(self):
        sessions = _newest_first(
            _session(peak_hour=2, days_ago=0),
            _session(peak_hour=2, days_ago=1),
            _session(peak_hour=2, days_ago=2),
            _session(peak_hour=1, days_ago=3),
            _session(peak_hour=3, days_ago=4),
        )
        result = generate_pattern_insights("u1", sessions, [])
        peak_tips = [i for i in result if "peaks" in i["title"]]
        assert peak_tips != []

    def test_peak_tip_type_is_tip(self):
        sessions = _newest_first(*[_session(peak_hour=2, days_ago=i) for i in range(5)])
        result = generate_pattern_insights("u1", sessions, [])
        peak_tips = [i for i in result if "peaks" in i["title"]]
        assert peak_tips[0]["type"] == "tip"

    def test_all_5_same_hour_triggers_tip(self):
        sessions = _newest_first(*[_session(peak_hour=2, days_ago=i) for i in range(5)])
        result = generate_pattern_insights("u1", sessions, [])
        assert [i for i in result if "peaks" in i["title"]] != []

    def test_all_different_hours_no_tip(self):
        sessions = _newest_first(
            _session(peak_hour=0, days_ago=0),
            _session(peak_hour=1, days_ago=1),
            _session(peak_hour=2, days_ago=2),
            _session(peak_hour=3, days_ago=3),
            _session(peak_hour=4, days_ago=4),
        )
        result = generate_pattern_insights("u1", sessions, [])
        assert [i for i in result if "peaks" in i["title"]] == []

    def test_only_2_sessions_share_peak_hour_no_tip(self):
        sessions = _newest_first(
            _session(peak_hour=2, days_ago=0),
            _session(peak_hour=2, days_ago=1),
            _session(peak_hour=1, days_ago=2),
            _session(peak_hour=1, days_ago=3),
            _session(peak_hour=3, days_ago=4),
        )
        result = generate_pattern_insights("u1", sessions, [])
        assert [i for i in result if "peaks" in i["title"]] == []

    def test_none_peak_hour_excluded_from_count(self):
        # Only 2 of 5 sessions have a non-None peak_hour — count < 3, no tip
        sessions = _newest_first(
            _session(peak_hour=2, days_ago=0),
            _session(peak_hour=2, days_ago=1),
            _session(peak_hour=None, days_ago=2),
            _session(peak_hour=None, days_ago=3),
            _session(peak_hour=None, days_ago=4),
        )
        result = generate_pattern_insights("u1", sessions, [])
        assert [i for i in result if "peaks" in i["title"]] == []


# ── Rule 4: Short sleep duration ─────────────────────────────────────────────

class TestShortSleepDuration:
    def test_3_of_5_short_nights_triggers_warning(self):
        sessions = _newest_first(
            _session(duration=300, days_ago=0),
            _session(duration=300, days_ago=1),
            _session(duration=300, days_ago=2),
            _session(duration=480, days_ago=3),
            _session(duration=480, days_ago=4),
        )
        result = generate_pattern_insights("u1", sessions, [])
        dur_warnings = [i for i in result if "Averaging only" in i["title"]]
        assert dur_warnings != []

    def test_duration_warning_type_is_warning(self):
        sessions = _newest_first(*[_session(duration=300, days_ago=i) for i in range(5)])
        result = generate_pattern_insights("u1", sessions, [])
        dur_warnings = [i for i in result if "Averaging only" in i["title"]]
        assert dur_warnings[0]["type"] == "warning"

    def test_all_5_short_triggers_warning(self):
        sessions = _newest_first(*[_session(duration=300, days_ago=i) for i in range(5)])
        result = generate_pattern_insights("u1", sessions, [])
        assert [i for i in result if "Averaging only" in i["title"]] != []

    def test_2_short_nights_no_warning(self):
        sessions = _newest_first(
            _session(duration=300, days_ago=0),
            _session(duration=300, days_ago=1),
            _session(duration=480, days_ago=2),
            _session(duration=480, days_ago=3),
            _session(duration=480, days_ago=4),
        )
        result = generate_pattern_insights("u1", sessions, [])
        assert [i for i in result if "Averaging only" in i["title"]] == []

    def test_duration_exactly_360_not_short(self):
        # Threshold is duration < 360; 360 exactly is NOT short
        sessions = _newest_first(*[_session(duration=360, days_ago=i) for i in range(5)])
        result = generate_pattern_insights("u1", sessions, [])
        assert [i for i in result if "Averaging only" in i["title"]] == []

    def test_duration_359_is_short(self):
        sessions = _newest_first(*[_session(duration=359, days_ago=i) for i in range(5)])
        result = generate_pattern_insights("u1", sessions, [])
        assert [i for i in result if "Averaging only" in i["title"]] != []

    def test_fewer_than_3_sessions_no_warning(self):
        sessions = _newest_first(
            _session(duration=200, days_ago=0),
            _session(duration=200, days_ago=1),
        )
        result = generate_pattern_insights("u1", sessions, [])
        assert [i for i in result if "Averaging only" in i["title"]] == []


# ── Rule 5: Recording streak ──────────────────────────────────────────────────

class TestRecordingStreak:
    def test_7_consecutive_nights_triggers_achievement(self):
        sessions = _newest_first(*[_session(days_ago=i) for i in range(7)])
        result = generate_pattern_insights("u1", sessions, [])
        streaks = [i for i in result if "streak" in i["title"]]
        assert streaks != []

    def test_streak_title_includes_day_count(self):
        sessions = _newest_first(*[_session(days_ago=i) for i in range(7)])
        result = generate_pattern_insights("u1", sessions, [])
        streaks = [i for i in result if "streak" in i["title"]]
        assert "7" in streaks[0]["title"]

    def test_streak_type_is_achievement(self):
        sessions = _newest_first(*[_session(days_ago=i) for i in range(7)])
        result = generate_pattern_insights("u1", sessions, [])
        streaks = [i for i in result if "streak" in i["title"]]
        assert streaks[0]["type"] == "achievement"

    def test_6_consecutive_nights_no_streak(self):
        sessions = _newest_first(*[_session(days_ago=i) for i in range(6)])
        result = generate_pattern_insights("u1", sessions, [])
        assert [i for i in result if "streak" in i["title"]] == []

    def test_gap_in_dates_breaks_streak(self):
        # 7 sessions but not consecutive — day 3 is missing
        sessions = _newest_first(*[_session(days_ago=d) for d in [0, 1, 2, 4, 5, 6, 7]])
        result = generate_pattern_insights("u1", sessions, [])
        assert [i for i in result if "streak" in i["title"]] == []

    def test_10_consecutive_nights_streak_shows_10(self):
        sessions = _newest_first(*[_session(days_ago=i) for i in range(10)])
        result = generate_pattern_insights("u1", sessions, [])
        streaks = [i for i in result if "streak" in i["title"]]
        assert "10" in streaks[0]["title"]


# ── Rule 6: Best day-of-week pattern ─────────────────────────────────────────

class TestDayOfWeekPattern:
    def _sessions_with_day_contrast(self) -> list:
        """
        Mondays (2025-05-05, -12, -19, -26) score 90;
        Fridays (2025-05-02, -09, -16, -23) score 55.
        Both days have 4 sessions — day_avgs diff = 35 >= 10.
        6 neutral sessions pad the total to 14+.
        """
        monday = date(2025, 5, 5)    # confirmed Monday
        friday = date(2025, 5, 2)    # confirmed Friday
        sessions = []
        for week in range(4):
            for base, s in [(monday, 90.0), (friday, 55.0)]:
                d = base - timedelta(weeks=week)
                sessions.append(_session(score=s, days_ago=(date.today() - d).days))
        for i in range(6):
            sessions.append(_session(score=70.0, days_ago=60 + i))
        return sorted(sessions, key=lambda s: s.started_at, reverse=True)

    def test_distinct_weekday_scores_trigger_tip(self):
        result = generate_pattern_insights("u1", self._sessions_with_day_contrast(), [])
        day_tips = [i for i in result if "best sleep nights" in i["title"]]
        assert day_tips != []

    def test_day_tip_type_is_tip(self):
        result = generate_pattern_insights("u1", self._sessions_with_day_contrast(), [])
        day_tips = [i for i in result if "best sleep nights" in i["title"]]
        assert day_tips[0]["type"] == "tip"

    def test_fewer_than_14_sessions_no_day_tip(self):
        sessions = _newest_first(*[_session(days_ago=i) for i in range(13)])
        result = generate_pattern_insights("u1", sessions, [])
        assert [i for i in result if "best sleep nights" in i["title"]] == []


# ── Rule 7: Alcohol correlation ───────────────────────────────────────────────

class TestAlcoholCorrelation:
    def _build(self, alc_score=60.0, clean_score=85.0):
        sessions = _newest_first(
            _session(score=alc_score,   days_ago=0),
            _session(score=alc_score,   days_ago=1),
            _session(score=alc_score,   days_ago=2),
            _session(score=clean_score, days_ago=3),
            _session(score=clean_score, days_ago=4),
            _session(score=clean_score, days_ago=5),
        )
        logs = [
            _log(days_ago=0, alcohol_units=2.0),
            _log(days_ago=1, alcohol_units=2.0),
            _log(days_ago=2, alcohol_units=2.0),
            _log(days_ago=3, alcohol_units=0.0),
            _log(days_ago=4, alcohol_units=0.0),
            _log(days_ago=5, alcohol_units=0.0),
        ]
        return sessions, logs

    def test_alcohol_correlation_triggers_tip(self):
        sessions, logs = self._build()
        result = generate_pattern_insights("u1", sessions, logs)
        assert [i for i in result if "alcohol" in i["title"].lower()] != []

    def test_alcohol_tip_type_is_tip(self):
        sessions, logs = self._build()
        result = generate_pattern_insights("u1", sessions, logs)
        tips = [i for i in result if "alcohol" in i["title"].lower()]
        assert tips[0]["type"] == "tip"

    def test_alcohol_tip_body_mentions_scores(self):
        sessions, logs = self._build()
        result = generate_pattern_insights("u1", sessions, logs)
        tips = [i for i in result if "alcohol" in i["title"].lower()]
        assert "60" in tips[0]["body"] or "85" in tips[0]["body"]

    def test_no_tip_when_difference_less_than_5(self):
        sessions, logs = self._build(alc_score=75.0, clean_score=78.0)
        result = generate_pattern_insights("u1", sessions, logs)
        assert [i for i in result if "alcohol" in i["title"].lower()] == []

    def test_fewer_than_3_alcohol_nights_no_tip(self):
        sessions = _newest_first(*[_session(score=60, days_ago=i) for i in range(6)])
        logs = [
            _log(days_ago=0, alcohol_units=2.0),
            _log(days_ago=1, alcohol_units=2.0),  # only 2 alcohol nights
            _log(days_ago=2, alcohol_units=0.0),
            _log(days_ago=3, alcohol_units=0.0),
            _log(days_ago=4, alcohol_units=0.0),
            _log(days_ago=5, alcohol_units=0.0),
        ]
        result = generate_pattern_insights("u1", sessions, logs)
        assert [i for i in result if "alcohol" in i["title"].lower()] == []

    def test_fewer_than_3_sober_nights_no_tip(self):
        sessions = _newest_first(*[_session(score=60, days_ago=i) for i in range(6)])
        logs = [
            _log(days_ago=0, alcohol_units=2.0),
            _log(days_ago=1, alcohol_units=2.0),
            _log(days_ago=2, alcohol_units=2.0),
            _log(days_ago=3, alcohol_units=2.0),
            _log(days_ago=4, alcohol_units=0.0),
            _log(days_ago=5, alcohol_units=0.0),  # only 2 sober nights
        ]
        result = generate_pattern_insights("u1", sessions, logs)
        assert [i for i in result if "alcohol" in i["title"].lower()] == []


# ── Rule 7: Exercise correlation ──────────────────────────────────────────────

class TestExerciseCorrelation:
    def _build(self, ex_score=85.0, rest_score=60.0):
        sessions = _newest_first(
            _session(score=ex_score,   days_ago=0),
            _session(score=ex_score,   days_ago=1),
            _session(score=ex_score,   days_ago=2),
            _session(score=rest_score, days_ago=3),
            _session(score=rest_score, days_ago=4),
            _session(score=rest_score, days_ago=5),
        )
        logs = [
            _log(days_ago=0, exercise_minutes=30),
            _log(days_ago=1, exercise_minutes=45),
            _log(days_ago=2, exercise_minutes=20),
            _log(days_ago=3, exercise_minutes=0),
            _log(days_ago=4, exercise_minutes=0),
            _log(days_ago=5, exercise_minutes=0),
        ]
        return sessions, logs

    def test_exercise_correlation_triggers_tip(self):
        sessions, logs = self._build()
        result = generate_pattern_insights("u1", sessions, logs)
        assert [i for i in result if "exercise" in i["title"].lower()] != []

    def test_exercise_tip_type_is_tip(self):
        sessions, logs = self._build()
        result = generate_pattern_insights("u1", sessions, logs)
        tips = [i for i in result if "exercise" in i["title"].lower()]
        assert tips[0]["type"] == "tip"

    def test_no_tip_when_difference_less_than_5(self):
        sessions, logs = self._build(ex_score=75.0, rest_score=73.0)
        result = generate_pattern_insights("u1", sessions, logs)
        assert [i for i in result if "exercise" in i["title"].lower()] == []

    def test_exercise_threshold_is_20_minutes(self):
        # 19 minutes does NOT count as exercise
        sessions = _newest_first(
            _session(score=85, days_ago=0),
            _session(score=85, days_ago=1),
            _session(score=85, days_ago=2),
            _session(score=60, days_ago=3),
            _session(score=60, days_ago=4),
            _session(score=60, days_ago=5),
        )
        logs = [
            _log(days_ago=0, exercise_minutes=19),  # below threshold
            _log(days_ago=1, exercise_minutes=19),
            _log(days_ago=2, exercise_minutes=19),
            _log(days_ago=3, exercise_minutes=0),
            _log(days_ago=4, exercise_minutes=0),
            _log(days_ago=5, exercise_minutes=0),
        ]
        result = generate_pattern_insights("u1", sessions, logs)
        assert [i for i in result if "exercise" in i["title"].lower()] == []

    def test_exercise_exactly_20_minutes_counts(self):
        sessions = _newest_first(
            _session(score=85, days_ago=0),
            _session(score=85, days_ago=1),
            _session(score=85, days_ago=2),
            _session(score=60, days_ago=3),
            _session(score=60, days_ago=4),
            _session(score=60, days_ago=5),
        )
        logs = [
            _log(days_ago=0, exercise_minutes=20),  # at threshold
            _log(days_ago=1, exercise_minutes=20),
            _log(days_ago=2, exercise_minutes=20),
            _log(days_ago=3, exercise_minutes=0),
            _log(days_ago=4, exercise_minutes=0),
            _log(days_ago=5, exercise_minutes=0),
        ]
        result = generate_pattern_insights("u1", sessions, logs)
        assert [i for i in result if "exercise" in i["title"].lower()] != []


# ── Rule 7: Stress correlation ────────────────────────────────────────────────

class TestStressCorrelation:
    def _build(self, hi_score=55.0, lo_score=85.0):
        # stress >= 4 → high; stress <= 2 → low
        sessions = _newest_first(
            _session(score=hi_score, days_ago=0),
            _session(score=hi_score, days_ago=1),
            _session(score=hi_score, days_ago=2),
            _session(score=lo_score, days_ago=3),
            _session(score=lo_score, days_ago=4),
            _session(score=lo_score, days_ago=5),
        )
        logs = [
            _log(days_ago=0, stress_level=5),
            _log(days_ago=1, stress_level=4),
            _log(days_ago=2, stress_level=4),
            _log(days_ago=3, stress_level=1),
            _log(days_ago=4, stress_level=2),
            _log(days_ago=5, stress_level=2),
        ]
        return sessions, logs

    def test_stress_correlation_triggers_tip(self):
        sessions, logs = self._build()
        result = generate_pattern_insights("u1", sessions, logs)
        assert [i for i in result if "stress" in i["title"].lower()] != []

    def test_stress_tip_type_is_tip(self):
        sessions, logs = self._build()
        result = generate_pattern_insights("u1", sessions, logs)
        tips = [i for i in result if "stress" in i["title"].lower()]
        assert tips[0]["type"] == "tip"

    def test_no_tip_when_difference_less_than_5(self):
        sessions, logs = self._build(hi_score=70.0, lo_score=73.0)
        result = generate_pattern_insights("u1", sessions, logs)
        assert [i for i in result if "stress" in i["title"].lower()] == []

    def test_stress_level_3_is_neither_high_nor_low(self):
        # Level 3 is neither >= 4 (high) nor <= 2 (low) — no groups form
        sessions = _newest_first(*[_session(score=70, days_ago=i) for i in range(6)])
        logs = [_log(days_ago=i, stress_level=3) for i in range(6)]
        result = generate_pattern_insights("u1", sessions, logs)
        assert [i for i in result if "stress" in i["title"].lower()] == []

    def test_fewer_than_3_high_stress_days_no_tip(self):
        sessions = _newest_first(*[_session(score=60, days_ago=i) for i in range(6)])
        logs = [
            _log(days_ago=0, stress_level=5),
            _log(days_ago=1, stress_level=4),  # only 2 high-stress
            _log(days_ago=2, stress_level=2),
            _log(days_ago=3, stress_level=1),
            _log(days_ago=4, stress_level=2),
            _log(days_ago=5, stress_level=1),
        ]
        result = generate_pattern_insights("u1", sessions, logs)
        assert [i for i in result if "stress" in i["title"].lower()] == []


# ── Result structure & priority sorting ──────────────────────────────────────

class TestResultStructure:
    def test_every_insight_has_required_keys(self):
        sessions = _newest_first(*[_session(score=50, days_ago=i) for i in range(3)])
        result = generate_pattern_insights("u1", sessions, [])
        for item in result:
            assert "type" in item
            assert "title" in item
            assert "body" in item
            assert "priority" in item

    def test_all_insight_types_are_valid(self):
        sessions = _newest_first(*[_session(score=50, days_ago=i) for i in range(3)])
        result = generate_pattern_insights("u1", sessions, [])
        for item in result:
            assert item["type"] in {"tip", "warning", "achievement"}

    def test_results_sorted_by_priority_descending(self):
        # Trigger multiple rules at once: bad streak + short duration + streak
        sessions = _newest_first(*[
            _session(score=50, duration=300, days_ago=i) for i in range(7)
        ])
        result = generate_pattern_insights("u1", sessions, [])
        priorities = [i["priority"] for i in result]
        assert priorities == sorted(priorities, reverse=True)

    def test_multiple_rules_fire_simultaneously(self):
        # Bad-night streak (rule 1) + short duration (rule 4) + recording streak (rule 5)
        sessions = _newest_first(*[
            _session(score=50, duration=300, days_ago=i) for i in range(7)
        ])
        result = generate_pattern_insights("u1", sessions, [])
        assert len(result) >= 2

    def test_no_duplicate_bad_night_insight(self):
        sessions = _newest_first(*[_session(score=50, days_ago=i) for i in range(10)])
        result = generate_pattern_insights("u1", sessions, [])
        assert len([i for i in result if "consecutive" in i["title"]]) == 1
