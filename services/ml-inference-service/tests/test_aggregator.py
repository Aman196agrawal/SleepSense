"""Tests for app/aggregator.py (FR-ML-004)."""
import pytest

from app.aggregator import aggregate


def _make_window(cls: str, intensity: float, start: float = 0.0) -> dict:
    return {
        "start_sec":  start,
        "end_sec":    start + 3.0,
        "class":      cls,
        "confidence": 0.75,
        "intensity":  intensity,
    }


# ── Empty input ────────────────────────────────────────────────────────────────

class TestAggregateEmpty:
    def test_empty_returns_zeros(self):
        result = aggregate([])
        assert result["snore_windows"] == 0
        assert result["total_windows"] == 0
        assert result["snore_ratio"]   == 0.0
        assert result["avg_intensity"] == 0.0
        assert result["max_intensity"] == 0.0
        assert result["per_event"]     == []

    def test_empty_has_all_keys(self):
        result = aggregate([])
        for key in ("snore_windows", "total_windows", "snore_ratio",
                    "avg_intensity", "max_intensity", "per_event"):
            assert key in result


# ── All silence ────────────────────────────────────────────────────────────────

class TestAggregateAllSilence:
    def _results(self):
        return [_make_window("silence", 0.0, i * 1.5) for i in range(5)]

    def test_snore_windows_zero(self):
        assert aggregate(self._results())["snore_windows"] == 0

    def test_snore_ratio_zero(self):
        assert aggregate(self._results())["snore_ratio"] == 0.0

    def test_avg_intensity_zero(self):
        assert aggregate(self._results())["avg_intensity"] == 0.0

    def test_total_windows_correct(self):
        assert aggregate(self._results())["total_windows"] == 5


# ── All snoring ────────────────────────────────────────────────────────────────

class TestAggregateAllSnoring:
    def _results(self):
        return [_make_window("snoring", 70.0 + i, i * 1.5) for i in range(4)]

    def test_snore_ratio_is_one(self):
        assert aggregate(self._results())["snore_ratio"] == 1.0

    def test_avg_intensity_correct(self):
        result = aggregate(self._results())
        expected_avg = round(sum(70.0 + i for i in range(4)) / 4, 1)
        assert result["avg_intensity"] == expected_avg

    def test_max_intensity_correct(self):
        result = aggregate(self._results())
        assert result["max_intensity"] == 73.0   # 70 + 3

    def test_snore_windows_equals_total(self):
        result = aggregate(self._results())
        assert result["snore_windows"] == result["total_windows"]


# ── Mixed results ─────────────────────────────────────────────────────────────

class TestAggregateMixed:
    def _results(self):
        return [
            _make_window("snoring",   80.0, 0.0),
            _make_window("breathing",  0.0, 1.5),
            _make_window("snoring",   60.0, 3.0),
            _make_window("silence",    0.0, 4.5),
        ]

    def test_snore_windows_count(self):
        assert aggregate(self._results())["snore_windows"] == 2

    def test_total_windows_count(self):
        assert aggregate(self._results())["total_windows"] == 4

    def test_snore_ratio(self):
        assert aggregate(self._results())["snore_ratio"] == 0.5

    def test_avg_intensity_only_snoring(self):
        result = aggregate(self._results())
        assert result["avg_intensity"] == 70.0   # (80+60)/2

    def test_max_intensity_all_windows(self):
        result = aggregate(self._results())
        assert result["max_intensity"] == 80.0

    def test_per_event_unchanged(self):
        events = self._results()
        result = aggregate(events)
        assert result["per_event"] is events


# ── Single window ─────────────────────────────────────────────────────────────

class TestAggregateSingleWindow:
    def test_single_snoring(self):
        result = aggregate([_make_window("snoring", 55.0)])
        assert result["snore_windows"]  == 1
        assert result["total_windows"]  == 1
        assert result["snore_ratio"]    == 1.0
        assert result["avg_intensity"]  == 55.0
        assert result["max_intensity"]  == 55.0

    def test_single_silence(self):
        result = aggregate([_make_window("silence", 0.0)])
        assert result["snore_windows"]  == 0
        assert result["snore_ratio"]    == 0.0
        assert result["avg_intensity"]  == 0.0


# ── Rounding / precision ──────────────────────────────────────────────────────

class TestAggregateRounding:
    def test_snore_ratio_rounded_to_3dp(self):
        results = [_make_window("snoring", 50.0, i * 1.5) for i in range(3)] + \
                  [_make_window("silence",  0.0, i * 1.5) for i in range(10)]
        ratio = aggregate(results)["snore_ratio"]
        assert ratio == round(ratio, 3)

    def test_avg_intensity_rounded_to_1dp(self):
        results = [_make_window("snoring", 33.333, i * 1.5) for i in range(3)]
        avg = aggregate(results)["avg_intensity"]
        assert avg == round(avg, 1)
