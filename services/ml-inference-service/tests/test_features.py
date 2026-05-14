"""Tests for app/features.py — 126-dim feature extraction."""
import numpy as np
import pytest

from app.features import FEATURE_DIM, extract_features, SR
from tests.conftest import make_wav, make_wav_silence, make_wav_loud
from app.preprocessing import decode_audio, segment_windows


def _window() -> np.ndarray:
    """Return a 3-second sine-wave PCM window at SR."""
    wav = make_wav(duration=3.0, freq=440.0, amplitude=0.5)
    return decode_audio(wav)


def _silence_window() -> np.ndarray:
    wav = make_wav_silence(duration=3.0)
    return decode_audio(wav)


def _loud_window() -> np.ndarray:
    wav = make_wav_loud(duration=3.0)
    return decode_audio(wav)


# ── Shape and type ─────────────────────────────────────────────────────────────

class TestExtractFeaturesShape:
    def test_output_dim(self):
        feats = extract_features(_window())
        assert feats.shape == (FEATURE_DIM,)

    def test_feature_dim_constant(self):
        assert FEATURE_DIM == 126

    def test_returns_float32(self):
        feats = extract_features(_window())
        assert feats.dtype == np.float32

    def test_all_finite(self):
        feats = extract_features(_window())
        assert np.all(np.isfinite(feats))

    def test_silence_all_finite(self):
        feats = extract_features(_silence_window())
        assert np.all(np.isfinite(feats))

    def test_loud_all_finite(self):
        feats = extract_features(_loud_window())
        assert np.all(np.isfinite(feats))


# ── Feature slices ─────────────────────────────────────────────────────────────

class TestFeatureSlices:
    def test_mfcc_slice_length(self):
        feats = extract_features(_window())
        assert feats[:40].shape == (40,)

    def test_delta_slice_length(self):
        feats = extract_features(_window())
        assert feats[40:80].shape == (40,)

    def test_delta2_slice_length(self):
        feats = extract_features(_window())
        assert feats[80:120].shape == (40,)

    def test_rms_feature_non_negative(self):
        feats = extract_features(_window())
        assert feats[120] >= 0.0

    def test_zcr_feature_in_range(self):
        feats = extract_features(_window())
        assert 0.0 <= feats[121] <= 1.0

    def test_centroid_positive(self):
        feats = extract_features(_window())
        assert feats[122] > 0.0

    def test_rolloff_positive(self):
        feats = extract_features(_window())
        assert feats[123] > 0.0

    def test_pitch_non_negative(self):
        feats = extract_features(_window())
        assert feats[124] >= 0.0

    def test_formant_f1_equals_half_centroid(self):
        feats = extract_features(_window())
        assert abs(feats[125] - feats[122] * 0.5) < 1e-3


# ── Behavioural ────────────────────────────────────────────────────────────────

class TestExtractFeaturesBehaviour:
    def test_loud_rms_greater_than_silence(self):
        loud_rms    = extract_features(_loud_window())[120]
        silence_rms = extract_features(_silence_window())[120]
        assert loud_rms > silence_rms

    def test_very_short_window_padded(self):
        # 4096 samples < 3s window but long enough for delta (needs ≥9 frames)
        short = np.ones(4096, dtype=np.float32)
        feats = extract_features(short)
        assert feats.shape == (FEATURE_DIM,)
        assert np.all(np.isfinite(feats))

    def test_deterministic(self):
        y = _window()
        f1 = extract_features(y)
        f2 = extract_features(y)
        np.testing.assert_array_equal(f1, f2)

    def test_custom_sr_accepted(self):
        y = _window()
        feats = extract_features(y, sr=8000)
        assert feats.shape == (FEATURE_DIM,)
        assert np.all(np.isfinite(feats))
