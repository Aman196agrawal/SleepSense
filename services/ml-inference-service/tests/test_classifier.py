"""Tests for app/classifier.py — SnoreClassifier stub behaviour."""
import numpy as np
import pytest

from app.classifier import CLASSES, SnoreClassifier


def _spec(energy_level: float) -> np.ndarray:
    """Return a (128, 128) spectrogram with given constant absolute value."""
    return np.full((128, 128), energy_level, dtype=np.float32)


# ── Instantiation ──────────────────────────────────────────────────────────────

class TestSnoreClassifierInit:
    def test_starts_as_stub(self):
        clf = SnoreClassifier()
        assert clf.is_stub is True

    def test_model_is_none_initially(self):
        clf = SnoreClassifier()
        assert clf._model is None


# ── Stub prediction — single spectrogram ──────────────────────────────────────

class TestStubPredict:
    def setup_method(self):
        self.clf = SnoreClassifier()

    def _predict(self, energy: float) -> dict:
        return self.clf._stub_predict(_spec(energy))

    def test_returns_required_keys(self):
        result = self._predict(0.5)
        for key in ("dominant_class", "confidence", "probabilities"):
            assert key in result

    def test_dominant_class_is_valid(self):
        for energy in (0.01, 0.1, 0.25, 0.5):
            result = self._predict(energy)
            assert result["dominant_class"] in CLASSES

    def test_high_energy_maps_to_snoring(self):
        assert self._predict(0.4)["dominant_class"] == "snoring"

    def test_medium_energy_maps_to_breathing(self):
        assert self._predict(0.25)["dominant_class"] == "breathing"

    def test_low_energy_maps_to_silence(self):
        assert self._predict(0.1)["dominant_class"] == "silence"

    def test_very_low_energy_maps_to_silence(self):
        assert self._predict(0.01)["dominant_class"] == "silence"

    def test_confidence_range(self):
        for energy in (0.01, 0.1, 0.25, 0.5):
            conf = self._predict(energy)["confidence"]
            assert 0.0 <= conf <= 1.0

    def test_probabilities_all_classes_present(self):
        probs = self._predict(0.5)["probabilities"]
        assert set(probs.keys()) == set(CLASSES)

    def test_probabilities_sum_to_one(self):
        probs = self._predict(0.25)["probabilities"]
        assert abs(sum(probs.values()) - 1.0) < 1e-3

    def test_dominant_class_matches_highest_probability(self):
        result = self._predict(0.5)
        best   = max(result["probabilities"], key=result["probabilities"].__getitem__)
        assert result["dominant_class"] == best

    def test_deterministic(self):
        spec = _spec(0.4)
        r1 = self.clf._stub_predict(spec)
        r2 = self.clf._stub_predict(spec)
        assert r1 == r2


# ── predict() (batch) ─────────────────────────────────────────────────────────

class TestClassifierPredict:
    def setup_method(self):
        self.clf = SnoreClassifier()

    def test_batch_length_matches_input(self):
        specs = [_spec(e) for e in (0.4, 0.2, 0.05)]
        results = self.clf.predict(specs)
        assert len(results) == 3

    def test_empty_batch_returns_empty(self):
        assert self.clf.predict([]) == []

    def test_single_spec_batch(self):
        results = self.clf.predict([_spec(0.5)])
        assert len(results) == 1
        assert results[0]["dominant_class"] in CLASSES

    def test_all_results_have_required_keys(self):
        specs = [_spec(e) for e in (0.01, 0.1, 0.25, 0.5)]
        for result in self.clf.predict(specs):
            for key in ("dominant_class", "confidence", "probabilities"):
                assert key in result


# ── load() fallback to stub ───────────────────────────────────────────────────

class TestClassifierLoad:
    def test_load_nonexistent_path_returns_false(self):
        clf = SnoreClassifier()
        assert clf.load("/nonexistent/model.pt") is False

    def test_remains_stub_after_failed_load(self):
        clf = SnoreClassifier()
        clf.load("/nonexistent/model.pt")
        assert clf.is_stub is True
