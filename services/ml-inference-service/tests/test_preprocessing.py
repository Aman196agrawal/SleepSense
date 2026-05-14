"""Tests for app/preprocessing.py (FR-ML-001)."""
import numpy as np
import pytest

from app.preprocessing import (
    SR,
    TARGET_SPEC,
    WINDOW_SECS,
    HOP_SECS,
    compute_mel_spectrogram,
    decode_audio,
    peak_normalize,
    preprocess_chunk,
    remove_dc_offset,
    segment_windows,
    trim_silence,
)
from tests.conftest import make_wav, make_wav_silence, make_wav_loud


# ── decode_audio ───────────────────────────────────────────────────────────────

class TestDecodeAudio:
    def test_returns_float32_array(self):
        y = decode_audio(make_wav(duration=1.0))
        assert y.dtype == np.float32

    def test_correct_sample_count(self):
        duration = 2.0
        y = decode_audio(make_wav(duration=duration))
        assert abs(len(y) - int(duration * SR)) <= SR // 10   # within 100 ms

    def test_values_in_minus1_to_1(self):
        y = decode_audio(make_wav(duration=1.0, amplitude=0.5))
        assert np.max(np.abs(y)) <= 1.01   # librosa normalises to float

    def test_empty_bytes_raises(self):
        with pytest.raises(Exception):
            decode_audio(b"")

    def test_silence_is_near_zero(self):
        y = decode_audio(make_wav_silence(duration=1.0))
        assert np.max(np.abs(y)) < 0.01


# ── remove_dc_offset ──────────────────────────────────────────────────────────

class TestRemoveDcOffset:
    def test_mean_near_zero(self):
        y = np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float32)
        out = remove_dc_offset(y)
        assert abs(np.mean(out)) < 1e-6

    def test_returns_float32(self):
        y = np.ones(100, dtype=np.float64)
        assert remove_dc_offset(y).dtype == np.float32

    def test_length_preserved(self):
        y = np.random.randn(1000).astype(np.float32)
        assert len(remove_dc_offset(y)) == 1000


# ── peak_normalize ────────────────────────────────────────────────────────────

class TestPeakNormalize:
    def test_peak_is_one(self):
        y = np.array([0.1, 0.5, 0.3, -0.2], dtype=np.float32)
        out = peak_normalize(y)
        assert abs(np.max(np.abs(out)) - 1.0) < 1e-5

    def test_silent_signal_unchanged(self):
        y = np.zeros(100, dtype=np.float32)
        out = peak_normalize(y)
        np.testing.assert_array_equal(out, y)

    def test_returns_float32(self):
        y = np.random.randn(100).astype(np.float64)
        assert peak_normalize(y).dtype == np.float32


# ── trim_silence ──────────────────────────────────────────────────────────────

class TestTrimSilence:
    def test_loud_signal_not_empty(self):
        y = decode_audio(make_wav_loud(duration=3.0))
        out = trim_silence(y)
        assert len(out) > 0

    def test_returns_float32(self):
        y = decode_audio(make_wav(duration=1.0))
        assert trim_silence(y).dtype == np.float32

    def test_full_silence_returns_original(self):
        y = np.zeros(SR * 2, dtype=np.float32)
        out = trim_silence(y)
        assert len(out) > 0   # must not return empty


# ── segment_windows ───────────────────────────────────────────────────────────

WIN_LEN = int(WINDOW_SECS * SR)
HOP_LEN = int(HOP_SECS * SR)


class TestSegmentWindows:
    def test_exact_one_window(self):
        y = np.zeros(WIN_LEN, dtype=np.float32)
        windows = segment_windows(y)
        assert len(windows) == 1
        assert len(windows[0]) == WIN_LEN

    def test_two_windows_with_overlap(self):
        # 4.5 s → 3 windows (0-3, 1.5-4.5)  with 50% overlap
        y = np.zeros(int(4.5 * SR), dtype=np.float32)
        windows = segment_windows(y)
        assert len(windows) == 2

    def test_three_windows(self):
        y = np.zeros(int(6.0 * SR), dtype=np.float32)
        windows = segment_windows(y)
        assert len(windows) == 3

    def test_short_audio_padded_to_one_window(self):
        y = np.ones(SR, dtype=np.float32)   # 1 s < WINDOW_SECS
        windows = segment_windows(y)
        assert len(windows) == 1
        assert len(windows[0]) == WIN_LEN
        # Original content preserved at the front
        np.testing.assert_array_equal(windows[0][:SR], y)
        # Padding is zero
        assert np.all(windows[0][SR:] == 0.0)

    def test_empty_audio_padded_to_one_window(self):
        y = np.zeros(0, dtype=np.float32)
        windows = segment_windows(y)
        assert len(windows) == 1
        assert len(windows[0]) == WIN_LEN

    def test_each_window_correct_length(self):
        y = np.zeros(int(30 * SR), dtype=np.float32)
        for w in segment_windows(y):
            assert len(w) == WIN_LEN


# ── compute_mel_spectrogram ───────────────────────────────────────────────────

class TestComputeMelSpectrogram:
    def test_output_shape(self):
        y = decode_audio(make_wav(duration=3.0))
        spec = compute_mel_spectrogram(y)
        assert spec.shape == TARGET_SPEC

    def test_values_in_minus1_to_1(self):
        y = decode_audio(make_wav(duration=3.0))
        spec = compute_mel_spectrogram(y)
        assert np.min(spec) >= -1.0
        assert np.max(spec) <= 1.0

    def test_returns_float32(self):
        y = decode_audio(make_wav(duration=3.0))
        spec = compute_mel_spectrogram(y)
        assert spec.dtype == np.float32

    def test_different_audio_produces_different_spectrograms(self):
        # power_to_db(ref=np.max) normalises peak to 0dB so overall amplitude
        # is equalised, but spectral content (freq distribution) still differs
        y_loud   = decode_audio(make_wav_loud(duration=3.0))
        y_silence = decode_audio(make_wav_silence(duration=3.0))
        s_loud   = compute_mel_spectrogram(y_loud)
        s_silent = compute_mel_spectrogram(y_silence)
        assert not np.allclose(s_loud, s_silent, atol=1e-3)


# ── preprocess_chunk (full pipeline) ──────────────────────────────────────────

class TestPreprocessChunk:
    def test_returns_two_lists(self):
        specs, windows = preprocess_chunk(make_wav(duration=3.0))
        assert isinstance(specs,   list)
        assert isinstance(windows, list)

    def test_same_number_of_specs_and_windows(self):
        specs, windows = preprocess_chunk(make_wav(duration=6.0))
        assert len(specs) == len(windows)

    def test_spectrogram_shape(self):
        specs, _ = preprocess_chunk(make_wav(duration=3.0))
        for s in specs:
            assert s.shape == TARGET_SPEC

    def test_window_length(self):
        _, windows = preprocess_chunk(make_wav(duration=3.0))
        for w in windows:
            assert len(w) == WIN_LEN

    def test_at_least_one_window(self):
        specs, _ = preprocess_chunk(make_wav(duration=1.0))   # short → padded
        assert len(specs) >= 1

    def test_30_second_chunk_produces_multiple_windows(self):
        specs, _ = preprocess_chunk(make_wav(duration=30.0))
        assert len(specs) > 1

    def test_empty_bytes_raises(self):
        with pytest.raises((ValueError, Exception)):
            preprocess_chunk(b"")

    def test_all_specs_finite(self):
        specs, _ = preprocess_chunk(make_wav(duration=3.0))
        for s in specs:
            assert np.all(np.isfinite(s))
