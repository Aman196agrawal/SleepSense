"""
Dataset builder for the SleepSense snore classifier.

Maps ESC-50 + snoring-dataset audio files into 4 target classes:
  0 = snoring
  1 = breathing
  2 = silence
  3 = ambient

ESC-50 class → our label mapping:
  28 (snoring)                         → 0  snoring
  [generated soft-breathing samples]   → 1  breathing
  [programmatically generated silence] → 2  silence
  all remaining ESC-50 classes         → 3  ambient
"""
import os
import random
import numpy as np
import pandas as pd
import librosa
import soundfile as sf
from pathlib import Path
from src.features import load_audio, audio_to_melspec, SAMPLE_RATE, WINDOW_SEC

CLASSES      = ["snoring", "breathing", "silence", "ambient"]
CLASS_TO_IDX = {c: i for i, c in enumerate(CLASSES)}

# ESC-50 target classes (numeric labels from ESC-50 meta CSV)
ESC50_SNORING_LABEL  = 28
ESC50_AMBIENT_LABELS = set(range(50)) - {28}  # everything except snoring


def generate_silence_sample(duration: float = WINDOW_SEC, sr: int = SAMPLE_RATE) -> np.ndarray:
    """Generate a near-silence clip: random amplitude Gaussian noise < -40 dBFS."""
    rms_target = 10 ** (-45 / 20)   # -45 dBFS
    noise = np.random.randn(int(sr * duration)).astype(np.float32)
    noise = noise / (noise.std() + 1e-9) * rms_target
    return noise


def build_esc50_dataframe(esc50_root: str) -> pd.DataFrame:
    """
    Returns a DataFrame with columns: path, label (0-3), class_name.
    esc50_root must contain audio/ and meta/esc50.csv.
    """
    meta = pd.read_csv(os.path.join(esc50_root, "meta", "esc50.csv"))
    rows = []
    audio_dir = os.path.join(esc50_root, "audio")

    for _, row in meta.iterrows():
        fpath = os.path.join(audio_dir, row["filename"])
        if not os.path.exists(fpath):
            continue
        target = row["target"]
        if target == ESC50_SNORING_LABEL:
            label = CLASS_TO_IDX["snoring"]
            cname = "snoring"
        else:
            label = CLASS_TO_IDX["ambient"]
            cname = "ambient"
        rows.append({"path": fpath, "label": label, "class_name": cname})

    df = pd.DataFrame(rows)
    return df


def add_snoring_dataset(df: pd.DataFrame, snoring_dir: str) -> pd.DataFrame:
    """
    Append samples from an external snoring dataset directory.
    Directory layout: snoring_dir/{snoring,non-snoring}/*.wav
    """
    rows = []
    snore_dir    = os.path.join(snoring_dir, "snoring")
    nonsnore_dir = os.path.join(snoring_dir, "non-snoring")

    for fpath in Path(snore_dir).glob("*.wav"):
        rows.append({"path": str(fpath), "label": CLASS_TO_IDX["snoring"], "class_name": "snoring"})
    for fpath in Path(nonsnore_dir).glob("*.wav"):
        rows.append({"path": str(fpath), "label": CLASS_TO_IDX["ambient"], "class_name": "ambient"})

    return pd.concat([df, pd.DataFrame(rows)], ignore_index=True)


def add_silence_samples(df: pd.DataFrame, n: int = 300, tmp_dir: str = "/tmp/silence") -> pd.DataFrame:
    """Generate n silence WAV files and add them to the dataframe."""
    os.makedirs(tmp_dir, exist_ok=True)
    rows = []
    for i in range(n):
        y = generate_silence_sample()
        fpath = os.path.join(tmp_dir, f"silence_{i:04d}.wav")
        sf.write(fpath, y, SAMPLE_RATE)
        rows.append({"path": fpath, "label": CLASS_TO_IDX["silence"], "class_name": "silence"})
    return pd.concat([df, pd.DataFrame(rows)], ignore_index=True)


class AudioAugmentor:
    """Stochastic augmentation applied during training only."""

    def __init__(self, sr: int = SAMPLE_RATE):
        self.sr = sr

    def __call__(self, y: np.ndarray) -> np.ndarray:
        if random.random() < 0.5:
            rate = random.uniform(0.85, 1.15)
            y = librosa.effects.time_stretch(y, rate=rate)
        if random.random() < 0.5:
            steps = random.uniform(-2, 2)
            y = librosa.effects.pitch_shift(y, sr=self.sr, n_steps=steps)
        if random.random() < 0.4:
            noise = np.random.randn(len(y)) * random.uniform(0.001, 0.01)
            y = y + noise.astype(y.dtype)
        if random.random() < 0.3:
            gain_db = random.uniform(-6, 6)
            y = y * (10 ** (gain_db / 20))
        # Re-trim/pad after augmentation
        target = int(self.sr * WINDOW_SEC)
        if len(y) < target:
            y = np.pad(y, (0, target - len(y)))
        return y[:target].astype(np.float32)
