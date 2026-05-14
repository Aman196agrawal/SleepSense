"""Tests for app/regressor.py — IntensityRegressor stub behaviour."""
import numpy as np
import pytest

from app.regressor import IntensityRegressor
from app.features import FEATURE_DIM


def _feats(rms: float = 0.5) -> np.ndarray:
    """Return a 126-dim feature vector with given RMS value at index 120."""
    f = np.zeros(FEATURE_DIM, dtype=np.float32)
    f[120] = rms
    return f


# ── Instantiation ──────────────────────────────────────────────────────────────

class TestIntensityRegressorInit:
    def test_starts_as_stub(self):
        reg = IntensityRegressor()
        assert reg.is_stub is True

    def test_model_is_none_initially(self):
        reg = IntensityRegressor()
        assert reg._model is None


# ── Stub prediction ───────────────────────────────────────────────────────────

class TestStubPredict:
    def setup_method(self):
        self.reg = IntensityRegressor()

    def test_returns_float(self):
        assert isinstance(self.reg._stub_predict(_feats(0.5)), float)

    def test_zero_rms_gives_zero_intensity(self):
        assert self.reg._stub_predict(_feats(0.0)) == 0.0

    def test_max_rms_clipped_to_100(self):
        assert self.reg._stub_predict(_feats(10.0)) == 100.0

    def test_half_amplitude_maps_near_50(self):
        # rms≈0.25 for amplitude=0.5 sine → intensity≈50
        intensity = self.reg._stub_predict(_feats(0.25))
        assert 40.0 <= intensity <= 60.0

    def test_output_range_0_to_100(self):
        for rms in np.linspace(0.0, 1.0, 11):
            out = self.reg._stub_predict(_feats(float(rms)))
            assert 0.0 <= out <= 100.0

    def test_monotone_increasing(self):
        prev = -1.0
        for rms in np.linspace(0.0, 0.5, 6):
            curr = self.reg._stub_predict(_feats(float(rms)))
            assert curr >= prev
            prev = curr

    def test_deterministic(self):
        f = _feats(0.3)
        assert self.reg._stub_predict(f) == self.reg._stub_predict(f)

    def test_rounded_to_1dp(self):
        out = self.reg._stub_predict(_feats(0.333))
        assert out == round(out, 1)

    def test_short_feature_vector_fallback(self):
        short = np.ones(5, dtype=np.float32) * 0.1
        out = self.reg._stub_predict(short)
        assert 0.0 <= out <= 100.0


# ── predict() public interface ────────────────────────────────────────────────

class TestRegressorPredict:
    def setup_method(self):
        self.reg = IntensityRegressor()

    def test_predict_returns_float(self):
        result = self.reg.predict(_feats(0.4))
        assert isinstance(result, float)

    def test_predict_in_range(self):
        result = self.reg.predict(_feats(0.4))
        assert 0.0 <= result <= 100.0

    def test_predict_uses_stub_when_no_model(self):
        assert self.reg.is_stub
        result = self.reg.predict(_feats(0.4))
        expected = self.reg._stub_predict(_feats(0.4))
        assert result == expected


# ── load() fallback to stub ───────────────────────────────────────────────────

class TestRegressorLoad:
    def test_load_nonexistent_returns_false(self):
        reg = IntensityRegressor()
        assert reg.load("/nonexistent/model.json") is False

    def test_remains_stub_after_failed_load(self):
        reg = IntensityRegressor()
        reg.load("/nonexistent/model.json")
        assert reg.is_stub is True
