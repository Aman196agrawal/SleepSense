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
  [125]    — Formant F1 approximation (centroid × 0.5)
"""
import numpy as np

SR     = 16_000
N_MFCC = 40
FEATURE_DIM = N_MFCC * 3 + 6   # = 126


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

    # Formant F1 approximation (half of spectral centroid as proxy)
    formant_f1 = centroid * 0.5

    features = np.concatenate([
        mfcc_mean, delta_mean, delta2_mean,
        [rms, zcr, centroid, rolloff, pitch, formant_f1],
    ])

    return np.nan_to_num(features, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)
