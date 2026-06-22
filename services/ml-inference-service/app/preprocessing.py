"""
Audio preprocessing pipeline (FR-ML-001).
Converts raw audio bytes into mel spectrograms + raw PCM windows
ready for the CNN classifier and MFCC feature extractor.
"""
import io
from typing import List, Tuple

import numpy as np

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
    The final partial window is zero-padded and kept (rather than discarded) so no
    trailing audio is lost; audio shorter than one window yields a single padded one."""
    win_len  = int(WINDOW_SECS * SR)
    hop_len  = int(HOP_SECS    * SR)
    windows: List[np.ndarray] = []
    start = 0
    last_end = 0
    while start + win_len <= len(y):
        windows.append(y[start : start + win_len])
        last_end = start + win_len
        start += hop_len
    # Only add a trailing window if real audio extends past the last full window's
    # end (i.e. it wasn't already covered). Avoids a redundant window on exact
    # multiples while still capturing genuine leftover audio.
    if last_end < len(y):
        pad  = np.zeros(win_len, dtype=np.float32)
        tail = y[start:]
        pad[:len(tail)] = tail
        windows.append(pad)
    if not windows:  # audio shorter than one window (or empty) → one padded window
        pad = np.zeros(win_len, dtype=np.float32)
        pad[:len(y)] = y
        windows.append(pad)
    return windows


# ── Steps 6-7: mel spectrogram ─────────────────────────────────────────────────

def compute_mel_spectrogram(y: np.ndarray) -> np.ndarray:
    """
    Compute a (128, 128) float32 mel spectrogram normalised to [0, 1].

    The time axis is fixed by padding/cropping — NOT resampling — so the temporal
    structure (snore periodicity) the CNN relies on is preserved rather than warped.
    """
    import librosa
    S     = librosa.feature.melspectrogram(y=y, sr=SR, n_mels=N_MELS, hop_length=HOP_LENGTH, n_fft=N_FFT)
    S_db  = librosa.power_to_db(S, ref=np.max)  # (N_MELS, T), range ≈ [-80, 0] dB

    target_frames = TARGET_SPEC[1]
    if S_db.shape[1] < target_frames:
        S_db = np.pad(
            S_db, ((0, 0), (0, target_frames - S_db.shape[1])),
            mode="constant", constant_values=-80.0,
        )
    elif S_db.shape[1] > target_frames:
        S_db = S_db[:, :target_frames]

    # Map the ~[-80, 0] dB range to [0, 1] (the convention used in training).
    return np.clip((S_db + 80.0) / 80.0, 0.0, 1.0).astype(np.float32)


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
    # NOTE: no global peak-normalize here. Normalizing the whole recording lets a
    # single loud transient (cough, door) set the gain and suppress everything else
    # all night. The spectrogram is normalized per-window via power_to_db(ref=np.max),
    # and the raw windows keep their absolute energy so RMS-based intensity stays valid.
    y = trim_silence(y)
    windows = segment_windows(y)
    spectrograms = [compute_mel_spectrogram(w) for w in windows]
    return spectrograms, windows
