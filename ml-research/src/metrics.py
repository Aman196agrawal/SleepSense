"""
Reference-free quality metrics for the snore-denoising feature.

We never have a clean ground-truth night recording (the noise is *in* the
source), so every metric here is **no-reference**: it judges a single waveform,
or compares RAW vs CLEANED, without needing a pristine target. That makes
"is the new denoiser actually better?" a number instead of an opinion — which is
exactly what a reviewer wants to see.

Core idea — frame the signal, split frames into *active* (snore present) vs
*gap* (quiet between snores) by energy percentile, then read out:

  • snr_active_gap_db   — loud snore frames vs quiet-gap frames. The headline.
  • noise_floor_db      — power of the quiet-gap frames (lower after cleaning = good).
  • snore_band_db       — power in the 80-1000 Hz snore band on active frames
                          (should be *retained*, not stripped, by cleaning).
  • musical_noise_flat  — spectral flatness of the gap frames. Spectral-subtraction
                          denoisers leave isolated tonal "musical noise" → flatness
                          DROPS. Higher (flatter) residual = cleaner-sounding.

`compare(raw, clean, sr)` returns the deltas (improvements); `metrics_table(...)`
renders RAW + any number of cleaned variants side by side for a notebook / report.

DNSMOS (a learned no-reference perceptual MOS) is supported as an *optional*
extra — only if `onnxruntime` and a model are available; otherwise it degrades
to "n/a" and the classical metrics still stand on their own.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import numpy as np
from scipy import signal

SAMPLE_RATE = 16_000          # keep in sync with denoise.py / features.py

# Frame analysis params for the energy-based active/gap split.
_FRAME_MS = 50.0
_HOP_MS = 25.0
# Percentile split: top frames are "active" (snore), bottom are "gap" (noise floor).
_ACTIVE_PCT = 90.0
_GAP_PCT = 10.0
# Snore energy band — fundamental ~80-100 Hz, harmonics up to ~1 kHz.
_SNORE_LO, _SNORE_HI = 80.0, 1000.0


# ── Framing helpers ───────────────────────────────────────────────────────────

def _frames(y: np.ndarray, sr: int):
    """Slice y into overlapping frames → (n_frames, frame_len) view."""
    flen = max(1, int(sr * _FRAME_MS / 1000.0))
    hop = max(1, int(sr * _HOP_MS / 1000.0))
    if len(y) < flen:
        y = np.pad(y, (0, flen - len(y)))
    n = 1 + (len(y) - flen) // hop
    idx = np.arange(flen)[None, :] + hop * np.arange(n)[:, None]
    return y[idx]


def _frame_power_db(y: np.ndarray, sr: int) -> np.ndarray:
    """Per-frame power in dB."""
    fr = _frames(y, sr)
    p = np.mean(fr.astype(np.float64) ** 2, axis=1)
    return 10.0 * np.log10(p + 1e-12)


def _active_gap_masks(pdb: np.ndarray):
    """Boolean masks for the loud (snore) and quiet (gap) frames by percentile."""
    hi = np.percentile(pdb, _ACTIVE_PCT)
    lo = np.percentile(pdb, _GAP_PCT)
    active = pdb >= hi
    gap = pdb <= lo
    # Guard against degenerate all-silent / all-equal frames.
    if not active.any():
        active = pdb >= np.median(pdb)
    if not gap.any():
        gap = pdb <= np.median(pdb)
    return active, gap


def _bandpass(y: np.ndarray, sr: int, lo: float, hi: float) -> np.ndarray:
    hi = min(hi, sr / 2 - 1)
    sos = signal.butter(4, [lo, hi], btype="bandpass", fs=sr, output="sos")
    return signal.sosfiltfilt(sos, y).astype(np.float32)


# ── Single-waveform metrics ───────────────────────────────────────────────────

@dataclass
class WaveformMetrics:
    """No-reference quality read-out for one waveform."""
    snr_active_gap_db: float    # loud-frame power − quiet-frame power
    noise_floor_db: float       # quiet-frame (gap) power
    snore_band_db: float        # 80-1000 Hz power on active frames
    musical_noise_flat: float   # spectral flatness of gap frames (1=flat/noise-like)

    def as_row(self) -> list[float]:
        return [self.snr_active_gap_db, self.noise_floor_db,
                self.snore_band_db, self.musical_noise_flat]


def _spectral_flatness(frames2d: np.ndarray) -> float:
    """Mean spectral flatness (geometric/arithmetic mean of the magnitude
    spectrum) over a set of frames. ~1 = white/flat; →0 = tonal/peaky.
    Musical-noise artifacts are tonal, so they drive this down."""
    if frames2d.size == 0:
        return float("nan")
    mag = np.abs(np.fft.rfft(frames2d * np.hanning(frames2d.shape[1]), axis=1)) + 1e-12
    gmean = np.exp(np.mean(np.log(mag), axis=1))
    amean = np.mean(mag, axis=1)
    return float(np.mean(gmean / amean))


def waveform_metrics(y: np.ndarray, sr: int = SAMPLE_RATE) -> WaveformMetrics:
    """Compute the no-reference metric set for a single waveform."""
    pdb = _frame_power_db(y, sr)
    active, gap = _active_gap_masks(pdb)

    snr = float(pdb[active].mean() - pdb[gap].mean())
    noise_floor = float(pdb[gap].mean())

    band = _bandpass(y, sr, _SNORE_LO, _SNORE_HI)
    band_pdb = _frame_power_db(band, sr)
    snore_band = float(band_pdb[active].mean())

    gap_frames = _frames(y, sr)[gap]
    flat = _spectral_flatness(gap_frames)

    return WaveformMetrics(snr, noise_floor, snore_band, flat)


# ── Optional: DNSMOS perceptual MOS (no-reference, learned) ────────────────────

def dnsmos_score(y: np.ndarray, sr: int = SAMPLE_RATE) -> float | None:
    """DNSMOS overall MOS (1-5, higher=better) if onnxruntime + a model are
    available; otherwise None. Model path via the DNSMOS_ONNX env var.

    Kept fully optional so the harness has no hard ML dependency — the classical
    metrics above stand on their own.
    """
    model_path = os.environ.get("DNSMOS_ONNX")
    if not model_path or not os.path.exists(model_path):
        return None
    try:
        import onnxruntime as ort  # noqa: F401
        import librosa
    except ImportError:
        return None
    try:
        sess = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
        y16 = librosa.resample(y, orig_sr=sr, target_sr=16_000) if sr != 16_000 else y
        # DNSMOS p.808 model: log-mel input, 9-second windows averaged.
        win = 16_000 * 9
        scores = []
        for start in range(0, max(1, len(y16) - win + 1), win):
            seg = y16[start:start + win]
            if len(seg) < win:
                seg = np.pad(seg, (0, win - len(seg)))
            mel = librosa.feature.melspectrogram(y=seg, sr=16_000, n_fft=321,
                                                 hop_length=160, n_mels=120)
            feat = librosa.power_to_db(mel).T[np.newaxis, ...].astype(np.float32)
            out = sess.run(None, {sess.get_inputs()[0].name: feat})[0]
            scores.append(float(np.ravel(out)[-1]))
        return float(np.mean(scores)) if scores else None
    except Exception:
        return None


# ── Comparison + reporting ─────────────────────────────────────────────────────

@dataclass
class DenoiseComparison:
    """RAW → CLEAN improvement deltas. Positive = better (except where noted)."""
    snr_improvement_db: float       # ↑ better — snore stands out more
    noise_floor_reduction_db: float # ↑ better — quieter gaps (raw_floor − clean_floor)
    snore_band_retention_db: float  # ~0 ideal — how much snore-band power was kept
    musical_noise_delta: float      # ↑ better — flatter (less tonal) residual


def compare(raw: np.ndarray, clean: np.ndarray,
            sr: int = SAMPLE_RATE) -> DenoiseComparison:
    """Improvement of `clean` over `raw` across the no-reference metrics."""
    r = waveform_metrics(raw, sr)
    c = waveform_metrics(clean, sr)
    return DenoiseComparison(
        snr_improvement_db=c.snr_active_gap_db - r.snr_active_gap_db,
        noise_floor_reduction_db=r.noise_floor_db - c.noise_floor_db,
        snore_band_retention_db=c.snore_band_db - r.snore_band_db,
        musical_noise_delta=c.musical_noise_flat - r.musical_noise_flat,
    )


def metrics_table(variants: dict[str, np.ndarray], sr: int = SAMPLE_RATE,
                  baseline: str = "RAW", dnsmos: bool = False) -> str:
    """Side-by-side metric table for {label: waveform}. The `baseline` row's SNR
    and noise-floor are used to show Δ for every other row. Returns a printable
    string. Set dnsmos=True to add a DNSMOS column (n/a if unavailable).

    Higher is better for: SNR, ΔSNR, NoiseRed, Flatness, DNSMOS.
    SnoreBand Δ near 0 is ideal (signal preserved, not stripped)."""
    rows = {label: waveform_metrics(y, sr) for label, y in variants.items()}
    base = rows.get(baseline)

    header = f"{'variant':<16}{'SNR(dB)':>9}{'dSNR':>8}{'NoiseFl':>9}" \
             f"{'NoiseRed':>9}{'SnoreBd':>9}{'Flat':>7}"
    if dnsmos:
        header += f"{'DNSMOS':>8}"
    lines = [header, "-" * len(header)]

    for label, m in rows.items():
        dsnr = m.snr_active_gap_db - base.snr_active_gap_db if base else 0.0
        nred = base.noise_floor_db - m.noise_floor_db if base else 0.0
        line = (f"{label:<16}{m.snr_active_gap_db:>9.2f}{dsnr:>+8.2f}"
                f"{m.noise_floor_db:>9.2f}{nred:>+9.2f}"
                f"{m.snore_band_db:>9.2f}{m.musical_noise_flat:>7.3f}")
        if dnsmos:
            s = dnsmos_score(variants[label], sr)
            line += f"{(f'{s:.2f}' if s is not None else 'n/a'):>8}"
        lines.append(line)
    return "\n".join(lines)


# ── Reference-based metric (synthetic scenes only — real nights have no clean) ─

def si_sdr(reference: np.ndarray, estimate: np.ndarray) -> float:
    """Scale-invariant signal-to-distortion ratio in dB (higher = better).

    The standard source-separation metric: projects `estimate` onto `reference`
    so a pure gain change scores identically, then measures residual distortion.
    Only usable where a clean reference exists (synthetic mixtures) — which is
    exactly why we build synthetic scenes."""
    n = min(len(reference), len(estimate))
    r = reference[:n].astype(np.float64)
    e = estimate[:n].astype(np.float64)
    r = r - r.mean()
    e = e - e.mean()
    s_target = (np.dot(e, r) / (np.dot(r, r) + 1e-12)) * r
    noise = e - s_target
    return float(10 * np.log10((np.sum(s_target ** 2) + 1e-12) /
                               (np.sum(noise ** 2) + 1e-12)))


# ── Synthetic test signal (validates the harness with no real recording) ───────

def synthetic_snore_scene(seconds: float = 30.0, sr: int = SAMPLE_RATE,
                          seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """Build a (noisy, clean) pair mimicking a phone night recording:
    periodic snore bursts (100 Hz fundamental + harmonics, breath-rate envelope)
    over AC sub-bass rumble (~30 Hz), 50 Hz mains hum, and broadband fan hiss.

    Returns (noisy, clean_snore_only) — the clean track is *only* available here
    because we synthesised it; real recordings have no such reference. Use it to
    sanity-check that the metrics move the right way when noise is removed.
    """
    rng = np.random.default_rng(seed)
    n = int(seconds * sr)
    t = np.arange(n) / sr

    # Snore: harmonic stack, gated by a ~0.25 Hz breathing envelope (one snore / ~4 s).
    breath = np.clip(np.sin(2 * np.pi * 0.25 * t), 0, None) ** 2
    snore = sum((1.0 / k) * np.sin(2 * np.pi * 100 * k * t) for k in range(1, 8))
    snore = (snore / np.max(np.abs(snore))) * breath * 0.6

    ac_rumble = 0.25 * np.sin(2 * np.pi * 30 * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.05 * t))
    mains = 0.08 * np.sin(2 * np.pi * 50 * t)
    fan = 0.05 * rng.standard_normal(n)

    noisy = (snore + ac_rumble + mains + fan).astype(np.float32)
    clean = snore.astype(np.float32)
    return noisy, clean


def synthetic_cycling_scene(seconds: float = 60.0, sr: int = SAMPLE_RATE,
                            seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """Two-state noise scene modelling the real failure mode: the AC CYCLES.

    Fan hiss + mains hum run all night; the AC (sub-bass rumble + band-limited
    100-600 Hz compressor noise) is ON for the first half only. A single
    quietest-window noise profile is measured in the AC-off half, so it
    under-subtracts the AC-on half — the case multi-profile denoising fixes.

    Returns (noisy, clean_snore_only).
    """
    rng = np.random.default_rng(seed)
    n = int(seconds * sr)
    t = np.arange(n) / sr

    breath = np.clip(np.sin(2 * np.pi * 0.25 * t), 0, None) ** 2
    snore = sum((1.0 / k) * np.sin(2 * np.pi * 100 * k * t) for k in range(1, 8))
    snore = (snore / np.max(np.abs(snore))) * breath * 0.6

    fan = 0.04 * rng.standard_normal(n)
    mains = 0.05 * np.sin(2 * np.pi * 50 * t)

    # AC on in the first half only: rumble + band-limited compressor noise.
    ac_on = (t < seconds / 2).astype(np.float32)
    rumble = 0.25 * np.sin(2 * np.pi * 30 * t)
    sos = signal.butter(4, [100, 600], btype="bandpass", fs=sr, output="sos")
    compressor = signal.sosfilt(sos, rng.standard_normal(n)) * 0.12
    ac = (rumble + compressor) * ac_on

    noisy = (snore + fan + mains + ac).astype(np.float32)
    return noisy, snore.astype(np.float32)
