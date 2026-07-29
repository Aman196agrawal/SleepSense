"""
PCEN snore spectrogram (SleepSense visualization + reusable feature front-end).

PCEN (Per-Channel Energy Normalization) is a per-frequency automatic gain control
followed by dynamic-range compression. Its AGC tracks a slowly-varying background
floor (the AC/fan hum that *overlaps* the snore band and that spectral subtraction
can't remove without breaking the snore) and lets the faster snore bursts pop above
it — so the snore stands out against a flattened background.

This module is a pure `waveform -> matrix` transform (no matplotlib), so the same
function can later feed the classifier front-end. `src/visualize.py` draws it.

STFT params mirror `src/features.py` so the picture matches the model's view; only
`fmax` differs (2 kHz here to focus on the snore band, vs 8 kHz for the model).
"""
from __future__ import annotations

import numpy as np
import librosa

SAMPLE_RATE = 16_000
N_FFT, HOP_LENGTH, N_MELS, F_MIN = 1024, 512, 128, 50
VIZ_FMAX = 2000.0          # snore energy lives below ~2 kHz; crop for a readable view

# PCEN is tuned for spectrograms in roughly int16-PCM magnitude range; float audio in
# [-1, 1] yields tiny mel values, so scale up (librosa's documented idiom) to keep the
# `bias`/`eps` terms in their intended regime.
PCEN_INPUT_SCALE = float(2 ** 31)

# Snore-tuned PCEN defaults (see the time_constant sweep in test_pcen.py).
PCEN_TIME_CONSTANT = 0.8   # AGC smoothing; slow enough to track the AC floor, fast
                           # enough that snore bursts (~0.5-2 s) pop above it.
                           #
                           # Validated corpus-wide by sweep_pcen.py: 179 windows of
                           # 60 s at a 5-minute stride over ~15 h (3 recordings), 62
                           # of them with >=6 dB active-gap spread. Ranked per window
                           # and aggregated by median rank:
                           #
                           #   by contrast : 0.8 best (median 2.0, top-3 on 79%)
                           #   by AUC      : 1.2 best (median 2.0, top-3 on 84%);
                           #                 0.8 third (top-3 on 60%)
                           #
                           # 0.8 or 1.2 — the two metrics disagree only between
                           # neighbours, and both are stable: the same pair wins at
                           # every activity threshold from 0 to 12 dB and on all three
                           # recordings individually. 0.8 is kept as it wins outright
                           # on one metric and is top-3 on the other. This supersedes
                           # the original single-window tuning, which happened to land
                           # on the same value for much weaker reasons.
                           #
                           # BUT — the harder question is whether to use PCEN at all.
                           # By the rank-AUC metric (scale- and monotone-invariant, so
                           # PCEN's compression cannot flatter it) PCEN separates snore
                           # from background better than plain log-mel on just 1 of 62
                           # live windows, and 0 of 38 above 8 dB spread. `contrast`
                           # is kinder (25/62) but it is a z-scored mean difference,
                           # which compression does move. Treat PCEN as a visualization
                           # that flattens the AC floor for the eye — NOT as a
                           # demonstrated front-end improvement for the classifier.
PCEN_GAIN = 0.98
PCEN_BIAS = 2.0
PCEN_POWER = 0.5
PCEN_EPS = 1e-6


def _mel_power(y: np.ndarray, sr: int, fmax: float) -> np.ndarray:
    """Magnitude mel spectrogram (power=1) with the features.py STFT geometry."""
    return librosa.feature.melspectrogram(
        y=y, sr=sr, n_fft=N_FFT, hop_length=HOP_LENGTH,
        n_mels=N_MELS, fmin=F_MIN, fmax=fmax, power=1.0)


def _axes(n_frames: int, sr: int, fmax: float):
    times = librosa.frames_to_time(np.arange(n_frames), sr=sr, hop_length=HOP_LENGTH)
    freqs = librosa.mel_frequencies(n_mels=N_MELS, fmin=F_MIN, fmax=fmax)
    return times, freqs


def pcen_spectrogram(y: np.ndarray, sr: int = SAMPLE_RATE, *, fmax: float = VIZ_FMAX,
                     time_constant: float = PCEN_TIME_CONSTANT, gain: float = PCEN_GAIN,
                     bias: float = PCEN_BIAS, power: float = PCEN_POWER,
                     eps: float = PCEN_EPS,
                     input_scale: float = PCEN_INPUT_SCALE):
    """Waveform -> PCEN matrix. Returns (M [n_mels x n_frames], times_s, mel_freqs_hz).

    Pure, deterministic, no I/O — this is the reuse seam for a future ML front-end.
    """
    S = _mel_power(y, sr, fmax)
    M = librosa.pcen(S * input_scale, sr=sr, hop_length=HOP_LENGTH, gain=gain,
                     bias=bias, power=power, time_constant=time_constant, eps=eps)
    times, freqs = _axes(M.shape[1], sr, fmax)
    return M.astype(np.float32), times, freqs


def logmel_spectrogram(y: np.ndarray, sr: int = SAMPLE_RATE, *, fmax: float = VIZ_FMAX):
    """Waveform -> log-mel (dB) matrix, same geometry as `pcen_spectrogram`, for the
    side-by-side baseline. Returns (S_db, times_s, mel_freqs_hz)."""
    S_db = librosa.power_to_db(_mel_power(y, sr, fmax), ref=np.max)
    times, freqs = _axes(S_db.shape[1], sr, fmax)
    return S_db.astype(np.float32), times, freqs


def snore_frame_energy(y: np.ndarray, sr: int = SAMPLE_RATE,
                       lo: float = 80.0, hi: float = 1400.0) -> np.ndarray:
    """Per-frame snore-band (80-1400 Hz) RMS in dB, aligned to the spectrogram frames.

    Used as a neutral, representation-independent activity reference so PCEN and
    log-mel are scored against the *same* active/gap frames (a fair comparison)."""
    from scipy import signal
    sos = signal.butter(4, [lo, min(hi, sr / 2 - 1)], btype="bandpass", fs=sr, output="sos")
    band = signal.sosfiltfilt(sos, y).astype(np.float32)
    rms = librosa.feature.rms(y=band, frame_length=N_FFT, hop_length=HOP_LENGTH)[0]
    return 20 * np.log10(rms + 1e-9)


def active_gap_contrast(M: np.ndarray, frame_energy: np.ndarray | None = None,
                        active_pct: float = 90.0, gap_pct: float = 10.0) -> float:
    """How far the snore stands above the background, in std units of the
    representation (so PCEN and log-mel are comparable despite different scales).

    `frame_energy` (e.g. from `snore_frame_energy`) selects active vs gap frames; if
    None, the matrix's own per-frame mean is used. Returns z(active) - z(gap)."""
    Mz = (M - M.mean()) / (M.std() + 1e-9)
    e = frame_energy if frame_energy is not None else M.mean(axis=0)
    n = min(len(e), Mz.shape[1])
    e, Mz = e[:n], Mz[:, :n]
    active = e >= np.percentile(e, active_pct)
    gap = e <= np.percentile(e, gap_pct)
    if not active.any() or not gap.any():
        return float("nan")
    return float(Mz[:, active].mean() - Mz[:, gap].mean())
