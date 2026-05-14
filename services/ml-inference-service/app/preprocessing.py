"""
Audio preprocessing pipeline (FR-ML-001).
Converts raw audio bytes into mel spectrograms + raw PCM windows
ready for the CNN classifier and MFCC feature extractor.
"""
import io
from typing import List, Tuple

import numpy as np
from scipy.ndimage import zoom

SR = 16_000          # target sample rate (Hz)
WINDOW_SECS = 3.0    # window length
HOP_SECS    = 1.5    # 50 % overlap → hop = 1.5 s
N_MELS      = 128
HOP_LENGTH  = 512
N_FFT       = 2048
SILENCE_TOP_DB  = 40.0          # trim silence quieter than -40 dBFS
TARGET_SPEC     = (128, 128)    # (mel_bins, time_frames)


# ── Step 1: decode ─────────────────────────────────────────────────────────────

def decode_audio(audio_bytes: bytes) -> np.ndarray:
    """Decode any librosa-supported format to float32 PCM at SR Hz mono."""
    import librosa
    y, _ = librosa.load(io.BytesIO(audio_bytes), sr=SR, mono=True)
    return y.astype(np.float32)


# ── Steps 2-4: clean ───────────────────────────────────────────────────────────

def remove_dc_offset(y: np.ndarray) -> np.ndarray:
    return (y - np.mean(y)).astype(np.float32)


def peak_normalize(y: np.ndarray) -> np.ndarray:
    peak = np.max(np.abs(y))
    return (y / peak if peak > 1e-8 else y).astype(np.float32)


def trim_silence(y: np.ndarray) -> np.ndarray:
    import librosa
    trimmed, _ = librosa.effects.trim(y, top_db=SILENCE_TOP_DB)
    return trimmed.astype(np.float32) if len(trimmed) > 0 else y


# ── Step 5: segment ────────────────────────────────────────────────────────────

def segment_windows(y: np.ndarray) -> List[np.ndarray]:
    """Split audio into WINDOW_SECS windows with 50 % overlap.
    If audio is shorter than one window, zero-pad and return one window."""
    win_len  = int(WINDOW_SECS * SR)
    hop_len  = int(HOP_SECS    * SR)
    windows: List[np.ndarray] = []
    start = 0
    while start + win_len <= len(y):
        windows.append(y[start : start + win_len])
        start += hop_len
    if not windows:
        pad = np.zeros(win_len, dtype=np.float32)
        pad[: len(y)] = y
        windows.append(pad)
    return windows


# ── Steps 6-7: mel spectrogram ─────────────────────────────────────────────────

def compute_mel_spectrogram(y: np.ndarray) -> np.ndarray:
    """
    Compute mel spectrogram and resize to TARGET_SPEC, normalised to [-1, 1].
    Output shape: (128, 128) float32.
    """
    import librosa
    S     = librosa.feature.melspectrogram(y=y, sr=SR, n_mels=N_MELS, hop_length=HOP_LENGTH, n_fft=N_FFT)
    S_db  = librosa.power_to_db(S, ref=np.max)  # shape (128, T)
    if S_db.shape != TARGET_SPEC:
        factors = (TARGET_SPEC[0] / S_db.shape[0], TARGET_SPEC[1] / S_db.shape[1])
        S_db = zoom(S_db, factors, order=1)
    # librosa range ≈ [-80, 0] dB → map to [-1, 1]
    return np.clip(S_db / 80.0, -1.0, 1.0).astype(np.float32)


# ── Full pipeline ──────────────────────────────────────────────────────────────

def preprocess_chunk(audio_bytes: bytes) -> Tuple[List[np.ndarray], List[np.ndarray]]:
    """
    Full preprocessing pipeline (FR-ML-001).

    Returns
    -------
    spectrograms : list of (128, 128) float32 — one per 3-second window, for the CNN.
    audio_windows: list of (SR*3,)  float32 — same windows as raw PCM, for MFCC extraction.
    """
    if not audio_bytes:
        raise ValueError("Empty audio bytes — nothing to process")
    y = decode_audio(audio_bytes)
    y = remove_dc_offset(y)
    y = peak_normalize(y)
    y = trim_silence(y)
    windows = segment_windows(y)
    spectrograms = [compute_mel_spectrogram(w) for w in windows]
    return spectrograms, windows
