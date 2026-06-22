"""
Acoustic feature extraction for the XGBoost intensity regressor (FR-ML-003).

Feature vector (126 dimensions):
  [0:40]   — 40 MFCC means
  [40:80]  — 40 delta-MFCC means
  [80:120] — 40 delta-delta-MFCC means
  [120]    — RMS energy
  [121]    — Zero-crossing rate
  [122]    — Spectral centroid (Hz)
  [123]    — Spectral rolloff (Hz)
  [124]    — Pitch F0 (Hz), 0.0 if unvoiced
  [125]    — Formant F1 (Hz) estimated via LPC, 0.0 if undetectable
"""
import numpy as np

SR     = 16_000
N_MFCC = 40
FEATURE_DIM = N_MFCC * 3 + 6   # = 126


def _estimate_f1(y: np.ndarray, sr: int) -> float:
    """Estimate the first formant (F1) via LPC root analysis.

    Replaces the old `centroid * 0.5` proxy, which was perfectly collinear with the
    spectral-centroid feature and therefore carried zero extra information.
    """
    try:
        import librosa
        # Rule-of-thumb LPC order for formant tracking: 2 + sr/1000.
        order = 2 + sr // 1000
        a = librosa.lpc(y.astype(np.float64) + 1e-9, order=order)
        roots = [r for r in np.roots(a) if np.imag(r) >= 0]
        freqs = sorted(
            np.arctan2(np.imag(r), np.real(r)) * (sr / (2 * np.pi)) for r in roots
        )
        # F1 is the lowest formant above ~90 Hz (skip near-DC roots).
        formants = [f for f in freqs if f > 90.0]
        return float(formants[0]) if formants else 0.0
    except Exception:
        return 0.0


def extract_features(y: np.ndarray, sr: int = SR) -> np.ndarray:
    """Extract 126-dim feature vector from a raw PCM audio window."""
    import librosa

    # Pad very short segments so MFCC has enough frames
    min_len = N_FFT = 2048
    if len(y) < min_len:
        y = np.pad(y, (0, min_len - len(y)))

    # ── MFCC family ─────────────────────────────────────────────────────────
    mfcc    = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=N_MFCC)
    delta   = librosa.feature.delta(mfcc)
    delta2  = librosa.feature.delta(mfcc, order=2)

    mfcc_mean   = np.mean(mfcc,   axis=1)   # (40,)
    delta_mean  = np.mean(delta,  axis=1)   # (40,)
    delta2_mean = np.mean(delta2, axis=1)   # (40,)

    # ── Scalar features ──────────────────────────────────────────────────────
    rms      = float(np.sqrt(np.mean(y ** 2)))
    zcr      = float(np.mean(librosa.feature.zero_crossing_rate(y)))
    centroid = float(np.mean(librosa.feature.spectral_centroid(y=y, sr=sr)))
    rolloff  = float(np.mean(librosa.feature.spectral_rolloff(y=y, sr=sr)))

    # Pitch via YIN
    try:
        f0     = librosa.yin(y, fmin=librosa.note_to_hz("C2"), fmax=librosa.note_to_hz("C7"), sr=sr)
        voiced = f0[f0 > 0]
        pitch  = float(np.nanmean(voiced)) if len(voiced) > 0 else 0.0
    except Exception:
        pitch = 0.0

    # Formant F1 via LPC (a real, non-redundant feature)
    formant_f1 = _estimate_f1(y, sr)

    features = np.concatenate([
        mfcc_mean, delta_mean, delta2_mean,
        [rms, zcr, centroid, rolloff, pitch, formant_f1],
    ])

    return np.nan_to_num(features, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)
