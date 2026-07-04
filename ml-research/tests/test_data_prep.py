"""
Tests for the leakage-free ESC-50 data prep (src/data_prep.py).

These pin the three train.py bugs found in review:
  1. breathing must be ESC-50 target 23 (was rain=10 / sea_waves=11)
  2. splits must follow ESC-50 folds (was random split over ×6-duplicated clips)
  3. oversampling + augmentation must touch ONLY the training split
"""
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.data_prep import (  # noqa: E402
    LABEL_AMBIENT,
    LABEL_BREATHING,
    LABEL_SILENCE,
    LABEL_SNORING,
    build_esc50_records,
    make_silence_records,
    oversample_with_augment,
    split_by_fold,
)


def fake_meta():
    """Minimal ESC-50 meta covering every mapping case, folds 1-5."""
    rows = []
    # 2 snoring clips per fold, 1 breathing, 1 rain, 1 sea_waves, 2 dogs
    for fold in range(1, 6):
        rows += [
            (f"{fold}-snore-A-28.wav", fold, 28, "snoring"),
            (f"{fold}-snore-B-28.wav", fold, 28, "snoring"),
            (f"{fold}-breath-A-23.wav", fold, 23, "breathing"),
            (f"{fold}-rain-A-10.wav", fold, 10, "rain"),
            (f"{fold}-waves-A-11.wav", fold, 11, "sea_waves"),
            (f"{fold}-dog-A-0.wav", fold, 0, "dog"),
            (f"{fold}-dog-B-0.wav", fold, 0, "dog"),
        ]
    return pd.DataFrame(rows, columns=["filename", "fold", "target", "category"])


def test_breathing_is_esc50_target_23():
    recs = build_esc50_records(fake_meta(), audio_dir="")
    by_name = {os.path.basename(r.path): r for r in recs}
    assert by_name["1-breath-A-23.wav"].label == LABEL_BREATHING


def test_rain_and_sea_waves_are_ambient_not_breathing():
    """Regression: train.py mapped targets {10, 11} (rain, sea_waves) to breathing."""
    recs = build_esc50_records(fake_meta(), audio_dir="")
    by_name = {os.path.basename(r.path): r for r in recs}
    assert by_name["1-rain-A-10.wav"].label == LABEL_AMBIENT
    assert by_name["1-waves-A-11.wav"].label == LABEL_AMBIENT


def test_snoring_and_ambient_mapping():
    recs = build_esc50_records(fake_meta(), audio_dir="")
    by_name = {os.path.basename(r.path): r for r in recs}
    assert by_name["2-snore-A-28.wav"].label == LABEL_SNORING
    assert by_name["3-dog-A-0.wav"].label == LABEL_AMBIENT


def test_records_are_not_duplicated_at_build_time():
    """Regression: train.py oversampled snoring ×6 BEFORE the split (leakage)."""
    recs = build_esc50_records(fake_meta(), audio_dir="")
    paths = [r.path for r in recs]
    assert len(paths) == len(set(paths))


def test_split_by_fold_uses_canonical_folds():
    recs = build_esc50_records(fake_meta(), audio_dir="")
    train, val, test = split_by_fold(recs)
    assert {r.fold for r in train} == {1, 2, 3}
    assert {r.fold for r in val} == {4}
    assert {r.fold for r in test} == {5}


def test_split_has_no_path_overlap():
    recs = build_esc50_records(fake_meta(), audio_dir="")
    train, val, test = split_by_fold(recs)
    t, v, s = {r.path for r in train}, {r.path for r in val}, {r.path for r in test}
    assert not (t & v) and not (t & s) and not (v & s)


def test_val_and_test_are_never_augmented():
    recs = build_esc50_records(fake_meta(), audio_dir="")
    train, val, test = split_by_fold(recs)
    train = oversample_with_augment(train, {LABEL_SNORING: 6, LABEL_BREATHING: 6})
    assert all(not r.augment for r in val)
    assert all(not r.augment for r in test)


def test_oversample_duplicates_are_augmented_train_only():
    recs = build_esc50_records(fake_meta(), audio_dir="")
    train, _, _ = split_by_fold(recs)
    n_snore_before = sum(r.label == LABEL_SNORING for r in train)
    over = oversample_with_augment(train, {LABEL_SNORING: 6})

    snore = [r for r in over if r.label == LABEL_SNORING]
    assert len(snore) == 6 * n_snore_before
    # one clean original per source clip, the rest augmented copies
    originals = [r for r in snore if not r.augment]
    assert len(originals) == n_snore_before
    # non-oversampled classes untouched
    assert sum(r.label == LABEL_AMBIENT for r in over) == \
        sum(r.label == LABEL_AMBIENT for r in train)


def test_silence_records_spread_across_all_folds():
    recs = make_silence_records("sil_dir", n=50)
    assert len(recs) == 50
    assert all(r.label == LABEL_SILENCE for r in recs)
    assert {r.fold for r in recs} == {1, 2, 3, 4, 5}
    train, val, test = split_by_fold(recs)
    assert train and val and test


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))


def test_silence_clips_have_varied_realistic_levels():
    """Regression: silence was always exactly -45 dBFS white noise, giving the
    model a trivial fixed-loudness shortcut."""
    import numpy as np
    from src.data_prep import generate_silence_clip

    rms_db = []
    for i in range(20):
        y = generate_silence_clip(seconds=1.0, sr=16_000, rng=np.random.default_rng(i))
        rms = float(np.sqrt(np.mean(y ** 2)))
        rms_db.append(20 * np.log10(rms + 1e-12))
    assert all(-60.0 <= v <= -35.0 for v in rms_db)
    assert max(rms_db) - min(rms_db) > 5.0  # levels actually vary
