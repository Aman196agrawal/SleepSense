"""Unit tests for app/rules.py — the 5 SRS rule evaluations."""
import pytest

from app.rules import evaluate_rules


def _eval(**kwargs):
    defaults = dict(
        sleep_quality_score  = 70.0,
        snore_ratio          = 0.3,
        avg_snore_intensity  = 40.0,
        duration_minutes     = 480,
        recent_scores        = [],
        recent_durations     = [],
        alcohol_units_today  = 0.0,
        sleep_position       = None,
    )
    defaults.update(kwargs)
    return evaluate_rules(**defaults)


def _rule_names(results):
    return [r["rule_name"] for r in results]


# ── Rule 1: POSITIONAL_SNORING ────────────────────────────────────────────────

class TestPositionalSnoring:
    def test_fires_back_sleeper_high_snore(self):
        results = _eval(sleep_position="back", snore_ratio=0.6)
        assert "POSITIONAL_SNORING" in _rule_names(results)

    def test_does_not_fire_side_sleeper(self):
        results = _eval(sleep_position="side", snore_ratio=0.8)
        assert "POSITIONAL_SNORING" not in _rule_names(results)

    def test_does_not_fire_back_low_snore(self):
        results = _eval(sleep_position="back", snore_ratio=0.3)
        assert "POSITIONAL_SNORING" not in _rule_names(results)

    def test_does_not_fire_no_position(self):
        results = _eval(sleep_position=None, snore_ratio=0.8)
        assert "POSITIONAL_SNORING" not in _rule_names(results)

    def test_fires_at_exact_threshold(self):
        results = _eval(sleep_position="back", snore_ratio=0.5)
        assert "POSITIONAL_SNORING" in _rule_names(results)

    def test_returns_tip_type(self):
        results = _eval(sleep_position="back", snore_ratio=0.6)
        match = next(r for r in results if r["rule_name"] == "POSITIONAL_SNORING")
        assert match["insight_type"] == "tip"
        assert match["priority"] == 8

    def test_action_url_contains_positional(self):
        results = _eval(sleep_position="back", snore_ratio=0.6)
        match = next(r for r in results if r["rule_name"] == "POSITIONAL_SNORING")
        assert "positional" in match["action_url"]


# ── Rule 2: ALCOHOL_CORRELATION ───────────────────────────────────────────────

class TestAlcoholCorrelation:
    def test_fires_alcohol_high_intensity(self):
        results = _eval(alcohol_units_today=2.0, avg_snore_intensity=75.0)
        assert "ALCOHOL_CORRELATION" in _rule_names(results)

    def test_does_not_fire_no_alcohol(self):
        results = _eval(alcohol_units_today=0.0, avg_snore_intensity=80.0)
        assert "ALCOHOL_CORRELATION" not in _rule_names(results)

    def test_does_not_fire_alcohol_low_intensity(self):
        results = _eval(alcohol_units_today=2.0, avg_snore_intensity=50.0)
        assert "ALCOHOL_CORRELATION" not in _rule_names(results)

    def test_fires_at_exact_threshold(self):
        results = _eval(alcohol_units_today=1.0, avg_snore_intensity=70.0)
        assert "ALCOHOL_CORRELATION" in _rule_names(results)

    def test_returns_tip_type_priority_7(self):
        results = _eval(alcohol_units_today=2.0, avg_snore_intensity=75.0)
        match = next(r for r in results if r["rule_name"] == "ALCOHOL_CORRELATION")
        assert match["insight_type"] == "tip"
        assert match["priority"] == 7

    def test_action_url_contains_alcohol(self):
        results = _eval(alcohol_units_today=2.0, avg_snore_intensity=75.0)
        match = next(r for r in results if r["rule_name"] == "ALCOHOL_CORRELATION")
        assert "alcohol" in match["action_url"]


# ── Rule 3: CHRONIC_SNORING ───────────────────────────────────────────────────

class TestChronicSnoring:
    def _chronic_scores(self):
        return [45.0, 42.0, 38.0, 41.0]   # 4 recent bad scores

    def test_fires_five_consecutive_bad_nights(self):
        results = _eval(
            sleep_quality_score=40.0,
            recent_scores=self._chronic_scores(),
        )
        assert "CHRONIC_SNORING" in _rule_names(results)

    def test_does_not_fire_only_four_bad(self):
        # only 3 of 4 recent are bad
        results = _eval(
            sleep_quality_score=40.0,
            recent_scores=[45.0, 42.0, 70.0, 41.0],   # 3rd is good
        )
        assert "CHRONIC_SNORING" not in _rule_names(results)

    def test_does_not_fire_current_night_good(self):
        results = _eval(
            sleep_quality_score=65.0,   # current is good
            recent_scores=self._chronic_scores(),
        )
        assert "CHRONIC_SNORING" not in _rule_names(results)

    def test_does_not_fire_empty_history(self):
        results = _eval(sleep_quality_score=40.0, recent_scores=[])
        assert "CHRONIC_SNORING" not in _rule_names(results)

    def test_does_not_fire_insufficient_history(self):
        results = _eval(sleep_quality_score=40.0, recent_scores=[42.0, 45.0, 38.0])
        assert "CHRONIC_SNORING" not in _rule_names(results)

    def test_has_highest_priority_9(self):
        results = _eval(
            sleep_quality_score=40.0,
            recent_scores=self._chronic_scores(),
        )
        match = next(r for r in results if r["rule_name"] == "CHRONIC_SNORING")
        assert match["priority"] == 9
        assert match["insight_type"] == "warning"

    def test_action_url_contains_specialist(self):
        results = _eval(
            sleep_quality_score=40.0,
            recent_scores=self._chronic_scores(),
        )
        match = next(r for r in results if r["rule_name"] == "CHRONIC_SNORING")
        assert "specialist" in match["action_url"]


# ── Rule 4: IMPROVEMENT_TREND ─────────────────────────────────────────────────

class TestImprovementTrend:
    def test_fires_when_score_exceeds_7night_avg_by_15(self):
        results = _eval(
            sleep_quality_score=85.0,
            recent_scores=[65.0] * 7,   # avg = 65, delta = 20
        )
        assert "IMPROVEMENT_TREND" in _rule_names(results)

    def test_does_not_fire_small_improvement(self):
        results = _eval(
            sleep_quality_score=75.0,
            recent_scores=[65.0] * 7,   # delta = 10 < 15
        )
        assert "IMPROVEMENT_TREND" not in _rule_names(results)

    def test_does_not_fire_insufficient_history(self):
        results = _eval(
            sleep_quality_score=90.0,
            recent_scores=[50.0] * 5,   # only 5 scores, need ≥ 7
        )
        assert "IMPROVEMENT_TREND" not in _rule_names(results)

    def test_does_not_fire_on_decline(self):
        results = _eval(
            sleep_quality_score=50.0,
            recent_scores=[75.0] * 7,   # current worse than average
        )
        assert "IMPROVEMENT_TREND" not in _rule_names(results)

    def test_fires_at_exact_threshold(self):
        # delta = 16 > 15 → fires
        results = _eval(
            sleep_quality_score=81.0,
            recent_scores=[65.0] * 7,
        )
        assert "IMPROVEMENT_TREND" in _rule_names(results)

    def test_returns_achievement_type_priority_6(self):
        results = _eval(
            sleep_quality_score=85.0,
            recent_scores=[65.0] * 7,
        )
        match = next(r for r in results if r["rule_name"] == "IMPROVEMENT_TREND")
        assert match["insight_type"] == "achievement"
        assert match["priority"] == 6

    def test_title_contains_score_info(self):
        results = _eval(
            sleep_quality_score=85.0,
            recent_scores=[65.0] * 7,
        )
        match = next(r for r in results if r["rule_name"] == "IMPROVEMENT_TREND")
        assert "85" in match["title"] or "20" in match["title"] or "pts" in match["title"]


# ── Rule 5: SLEEP_DEBT ────────────────────────────────────────────────────────

class TestSleepDebt:
    def test_fires_three_of_five_short(self):
        results = _eval(recent_durations=[300, 320, 310, 420, 410])   # 3 < 6h
        assert "SLEEP_DEBT" in _rule_names(results)

    def test_does_not_fire_two_of_five_short(self):
        results = _eval(recent_durations=[300, 320, 420, 450, 480])   # 2 < 6h
        assert "SLEEP_DEBT" not in _rule_names(results)

    def test_does_not_fire_insufficient_history(self):
        results = _eval(recent_durations=[300, 320, 310])   # only 3, need ≥ 5
        assert "SLEEP_DEBT" not in _rule_names(results)

    def test_fires_all_five_short(self):
        results = _eval(recent_durations=[300, 310, 320, 330, 340])
        assert "SLEEP_DEBT" in _rule_names(results)

    def test_returns_warning_type_priority_7(self):
        results = _eval(recent_durations=[300, 320, 310, 420, 410])
        match = next(r for r in results if r["rule_name"] == "SLEEP_DEBT")
        assert match["insight_type"] == "warning"
        assert match["priority"] == 7

    def test_action_url_contains_hygiene(self):
        results = _eval(recent_durations=[300, 320, 310, 420, 410])
        match = next(r for r in results if r["rule_name"] == "SLEEP_DEBT")
        assert "hygiene" in match["action_url"]


# ── Priority, limits, and edge cases ─────────────────────────────────────────

class TestPriorityAndLimits:
    def test_returns_at_most_three(self):
        # Fire all 5 rules simultaneously
        results = evaluate_rules(
            sleep_quality_score  = 40.0,    # triggers CHRONIC_SNORING
            snore_ratio          = 0.7,     # triggers POSITIONAL_SNORING
            avg_snore_intensity  = 80.0,    # triggers ALCOHOL_CORRELATION
            duration_minutes     = 480,
            recent_scores        = [45.0, 42.0, 38.0, 41.0],   # CHRONIC
            recent_durations     = [300, 310, 320, 420, 410],   # SLEEP_DEBT
            alcohol_units_today  = 2.0,     # ALCOHOL_CORRELATION
            sleep_position       = "back",  # POSITIONAL_SNORING
        )
        assert len(results) <= 3

    def test_highest_priority_first(self):
        results = evaluate_rules(
            sleep_quality_score  = 40.0,
            snore_ratio          = 0.7,
            avg_snore_intensity  = 80.0,
            duration_minutes     = 480,
            recent_scores        = [45.0, 42.0, 38.0, 41.0],
            recent_durations     = [300, 310, 320, 420, 410],
            alcohol_units_today  = 2.0,
            sleep_position       = "back",
        )
        priorities = [r["priority"] for r in results]
        assert priorities == sorted(priorities, reverse=True)

    def test_chronic_snoring_appears_first(self):
        results = evaluate_rules(
            sleep_quality_score  = 40.0,
            snore_ratio          = 0.7,
            avg_snore_intensity  = 80.0,
            duration_minutes     = 480,
            recent_scores        = [45.0, 42.0, 38.0, 41.0],
            recent_durations     = [300, 310, 320, 420, 410],
            alcohol_units_today  = 2.0,
            sleep_position       = "back",
        )
        assert results[0]["rule_name"] == "CHRONIC_SNORING"

    def test_no_rules_fire_empty_list(self):
        results = evaluate_rules(
            sleep_quality_score  = 85.0,
            snore_ratio          = 0.1,
            avg_snore_intensity  = 20.0,
            duration_minutes     = 490,
            recent_scores        = [80.0, 82.0],
            recent_durations     = [480, 490],
            alcohol_units_today  = 0.0,
            sleep_position       = "side",
        )
        assert results == []

    def test_single_rule_returns_one(self):
        results = evaluate_rules(
            sleep_quality_score  = 80.0,
            snore_ratio          = 0.6,
            avg_snore_intensity  = 30.0,
            duration_minutes     = 480,
            recent_scores        = [],
            recent_durations     = [],
            alcohol_units_today  = 0.0,
            sleep_position       = "back",   # only POSITIONAL_SNORING fires
        )
        assert len(results) == 1
        assert results[0]["rule_name"] == "POSITIONAL_SNORING"

    def test_all_results_have_required_keys(self):
        results = evaluate_rules(
            sleep_quality_score  = 80.0,
            snore_ratio          = 0.6,
            avg_snore_intensity  = 30.0,
            duration_minutes     = 480,
            recent_scores        = [],
            recent_durations     = [],
            alcohol_units_today  = 0.0,
            sleep_position       = "back",
        )
        for r in results:
            for key in ("rule_name", "insight_type", "priority", "title", "body", "action_url"):
                assert key in r
