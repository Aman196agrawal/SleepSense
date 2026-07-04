"""
Audio feature extraction for the SleepSense snore classifier.
Converts raw audio (WAV/Opus) into 128×128 log-mel spectrograms.
"""
import numpy as np
import librosa

# ── Constants (must match model input exactly) ──────────────────────────────
SAMPLE_RATE   = 16_000   # 16 kHz mono
WINDOW_SEC    = 3.0      # 3-second analysis window
N_MELS        = 128
N_FFT         = 1024
HOP_LENGTH    = 512
F_MIN         = 50       # Hz  — below snoring fundamental
F_MAX         = 8_000    # Hz  — above most snoring harmonics
IMG_SIZE      = 128      # final spectrogram is 128×128 pixels
DB_REF        = 1.0
TOP_DB        = 80.0


def load_audio(path: str, offset: float = 0.0, duration: float = WINDOW_SEC) -> np.ndarray:
    """Load audio file, resample to 16 kHz mono, pad/trim to WINDOW_SEC."""
    y, sr = librosa.load(path, sr=SAMPLE_RATE, mono=True,
                         offset=offset, duration=duration)
    target_len = int(SAMPLE_RATE * WINDOW_SEC)
    if len(y) < target_len:
        y = np.pad(y, (0, target_len - len(y)))
    else:
        y = y[:target_len]
    return y


def audio_to_melspec(y: np.ndarray) -> np.ndarray:
    """
    Convert waveform → log-mel spectrogram normalised to [0, 1].
    Output shape: (IMG_SIZE, IMG_SIZE, 1) — single channel for EfficientNet.
    """
    mel = librosa.feature.melspectrogram(
        y=y, sr=SAMPLE_RATE,
        n_fft=N_FFT, hop_length=HOP_LENGTH,
        n_mels=N_MELS, fmin=F_MIN, fmax=F_MAX
    )
    log_mel = librosa.power_to_db(mel, ref=DB_REF, top_db=TOP_DB)

    # Resize to IMG_SIZE × IMG_SIZE using bilinear interpolation
    import cv2
    img = cv2.resize(log_mel, (IMG_SIZE, IMG_SIZE), interpolation=cv2.INTER_LINEAR)

    # Normalise to [0, 1]
    img = (img - img.min()) / (img.max() - img.min() + 1e-8)

    return img[..., np.newaxis].astype(np.float32)   # (128, 128, 1)


def extract_mfcc_features(y: np.ndarray) -> np.ndarray:
    """
    Extract MFCC feature vector for the XGBoost intensity regressor.
    Returns a 1-D vector of 124 features:
      40 MFCCs (mean) + 40 delta-MFCCs (mean) + 40 delta²-MFCCs (mean)
      + RMS + ZCR + spectral centroid + spectral rolloff
    """
    mfcc        = librosa.feature.mfcc(y=y, sr=SAMPLE_RATE, n_mfcc=40)
    delta       = librosa.feature.delta(mfcc)
    delta2      = librosa.feature.delta(mfcc, order=2)
    rms         = librosa.feature.rms(y=y).mean()
    zcr         = librosa.feature.zero_crossing_rate(y).mean()
    spec_cent   = librosa.feature.spectral_centroid(y=y, sr=SAMPLE_RATE).mean()
    spec_roll   = librosa.feature.spectral_rolloff(y=y, sr=SAMPLE_RATE).mean()

    feats = np.concatenate([
        mfcc.mean(axis=1),
        delta.mean(axis=1),
        delta2.mean(axis=1),
        [rms, zcr, spec_cent, spec_roll],
    ])
    return feats.astype(np.float32)   # (124,)
