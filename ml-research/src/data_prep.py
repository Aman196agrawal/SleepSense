"""
Leakage-free ESC-50 data prep for the snore classifier.

Fixes three bugs in the original train.py data pipeline:
  1. breathing is ESC-50 target 23 (was rain=10 / sea_waves=11, and real
     breathing clips were polluting the ambient class)
  2. splits follow the canonical ESC-50 folds (train=1-3, val=4, test=5) so
     clips cut from the same source recording never straddle splits
  3. oversampling + augmentation happen AFTER the split, on the training
     records only — val/test stay clean and un-augmented

`train.py` consumes these records; tests in tests/test_data_prep.py pin the
behavior.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

LABEL_SNORING = 0
LABEL_BREATHING = 1
LABEL_SILENCE = 2
LABEL_AMBIENT = 3

ESC50_TARGET_SNORING = 28
ESC50_TARGET_BREATHING = 23

TRAIN_FOLDS, VAL_FOLDS, TEST_FOLDS = {1, 2, 3}, {4}, {5}


@dataclass(frozen=True)
class Record:
    path: str
    label: int
    fold: int
    augment: bool = False


def build_esc50_records(meta: pd.DataFrame, audio_dir: str) -> list[Record]:
    """One Record per ESC-50 clip (no duplication here — that would leak)."""
    records = []
    for _, row in meta.iterrows():
        if row["target"] == ESC50_TARGET_SNORING:
            label = LABEL_SNORING
        elif row["target"] == ESC50_TARGET_BREATHING:
            label = LABEL_BREATHING
        else:
            label = LABEL_AMBIENT
        records.append(Record(path=os.path.join(audio_dir, row["filename"]),
                              label=label, fold=int(row["fold"])))
    return records


def make_silence_records(sil_dir: str, n: int) -> list[Record]:
    """Synthetic-silence records, dealt round-robin across folds 1-5 so every
    split contains silence."""
    return [Record(path=os.path.join(sil_dir, f"sil_{i:04d}.wav"),
                   label=LABEL_SILENCE, fold=(i % 5) + 1) for i in range(n)]


def generate_silence_clip(seconds: float, sr: int,
                          rng: np.random.Generator | None = None) -> np.ndarray:
    """Near-silence clip at a RANDOM level in [-58, -38] dBFS — a fixed level
    would hand the model a trivial loudness shortcut for the silence class."""
    rng = rng if rng is not None else np.random.default_rng()
    rms = 10 ** (rng.uniform(-58.0, -38.0) / 20.0)
    noise = rng.standard_normal(int(sr * seconds)).astype(np.float32)
    return noise / (np.sqrt(np.mean(noise ** 2)) + 1e-9) * rms


def split_by_fold(records: list[Record]) -> tuple[list[Record], list[Record], list[Record]]:
    """Canonical ESC-50 fold split: train=folds 1-3, val=fold 4, test=fold 5."""
    train = [r for r in records if r.fold in TRAIN_FOLDS]
    val = [r for r in records if r.fold in VAL_FOLDS]
    test = [r for r in records if r.fold in TEST_FOLDS]
    return train, val, test


def oversample_with_augment(train: list[Record], factors: dict[int, int]) -> list[Record]:
    """Oversample minority classes in the TRAINING split only.

    For a class with factor k, each source clip yields 1 clean original plus
    k-1 augmented copies. Classes not in `factors` pass through untouched.
    """
    out = []
    for r in train:
        out.append(r)
        for _ in range(factors.get(r.label, 1) - 1):
            out.append(replace(r, augment=True))
    return out
