"""
Tests for the new cleaning methods (round 2 of the denoise work):

  * si_sdr                — reference-based scale-invariant SDR (metrics.py);
                            lets synthetic-scene experiments report a real
                            separation metric instead of only no-reference ones
  * synthetic_cycling_scene — two-state noise fixture: fan hiss all night,
                            AC (rumble + low-mid band noise) only in the first
                            half. Models the real "AC cycles on/off" failure.
  * multi_profile_denoise — k noise profiles clustered from the gaps, applied
                            per time region; must beat a single global profile
                            on cycling noise (the known weakness of `safe`)
  * mmse_lsa_denoise      — Ephraim-Malah MMSE log-spectral-amplitude denoiser
  * nmf_denoise           — semi-supervised NMF: noise dictionary learned from
                            the gaps, free components capture the snore
"""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.metrics import si_sdr, synthetic_cycling_scene, synthetic_snore_scene  # noqa: E402
from src.denoise import multi_profile_denoise, mmse_lsa_denoise, nmf_denoise  # noqa: E402

SR = 16_000


# ── si_sdr ─────────────────────────────────────────────────────────────────────

def test_si_sdr_perfect_reconstruction_is_high():
    _, clean = synthetic_snore_scene(seconds=5.0)
    assert si_sdr(clean, clean.copy()) > 50.0


def test_si_sdr_is_scale_invariant():
    # Test at moderate SNR — at perfect reconstruction the metric is dominated
    # by float rounding and any tolerance would be meaningless.
    noisy, clean = synthetic_snore_scene(seconds=5.0)
    assert si_sdr(clean, noisy * 0.1) == pytest.approx(si_sdr(clean, noisy * 3.0), abs=1e-6)


def test_si_sdr_noisy_is_worse_than_clean():
    noisy, clean = synthetic_snore_scene(seconds=5.0)
    assert si_sdr(clean, noisy) < si_sdr(clean, clean.copy())


# ── two-state synthetic fixture ────────────────────────────────────────────────

def test_cycling_scene_first_half_is_noisier():
    noisy, clean = synthetic_cycling_scene(seconds=40.0)
    n = len(noisy) // 2
    resid_on, resid_off = noisy[:n] - clean[:n], noisy[n:] - clean[n:]
    p = lambda x: 10 * np.log10(np.mean(x ** 2) + 1e-12)
    assert p(resid_on) > p(resid_off) + 3.0  # AC adds >=3 dB of noise


# ── multi-profile denoise ──────────────────────────────────────────────────────

def test_local_gap_profile_beats_old_global_quietest_window():
    """The headline: with AC cycling, the old global quietest-window profile is
    always measured AC-off, so the AC-on half is under-subtracted. A profile
    built from LOCALLY-detected gaps (samples both noise states) must win.

    (Experimental note, verified on this scene: the local-gap pooled profile is
    what delivers the gain — k-means splitting into per-state profiles adds
    nothing further, because a sharper profile also erodes more low-level snore
    in the overlapping band. Hence the companion non-regression test.)"""
    import noisereduce as nr
    from src.denoise import _auto_noise_clip

    noisy, clean = synthetic_cycling_scene(seconds=40.0)
    old_clip = _auto_noise_clip(noisy, SR)  # global quietest window = AC-off only
    old = nr.reduce_noise(y=noisy, sr=SR, stationary=True, y_noise=old_clip,
                          prop_decrease=0.9).astype(np.float32)
    new = multi_profile_denoise(noisy, SR, n_profiles=1)
    assert si_sdr(clean, new) > si_sdr(clean, old) + 2.0


def test_profile_clustering_does_not_regress_pooled():
    noisy, clean = synthetic_cycling_scene(seconds=40.0)
    pooled = multi_profile_denoise(noisy, SR, n_profiles=1)
    multi = multi_profile_denoise(noisy, SR, n_profiles=2)
    assert si_sdr(clean, multi) > si_sdr(clean, pooled) - 1.0


def test_multi_profile_improves_over_raw():
    noisy, clean = synthetic_cycling_scene(seconds=40.0)
    out = multi_profile_denoise(noisy, SR, n_profiles=2)
    assert si_sdr(clean, out) > si_sdr(clean, noisy) + 3.0


def test_multi_profile_preserves_length_and_dtype():
    noisy, _ = synthetic_cycling_scene(seconds=20.0)
    out = multi_profile_denoise(noisy, SR, n_profiles=2)
    assert out.shape == noisy.shape and out.dtype == np.float32


# ── MMSE-LSA ───────────────────────────────────────────────────────────────────

def test_mmse_lsa_improves_over_raw():
    noisy, clean = synthetic_snore_scene(seconds=20.0)
    out = mmse_lsa_denoise(noisy, SR)
    assert si_sdr(clean, out) > si_sdr(clean, noisy) + 3.0


def test_mmse_lsa_preserves_length_and_dtype():
    noisy, _ = synthetic_snore_scene(seconds=10.0)
    out = mmse_lsa_denoise(noisy, SR)
    assert out.shape == noisy.shape and out.dtype == np.float32


# ── semi-supervised NMF ────────────────────────────────────────────────────────

def test_nmf_improves_over_raw():
    noisy, clean = synthetic_snore_scene(seconds=20.0)
    out = nmf_denoise(noisy, SR)
    assert si_sdr(clean, out) > si_sdr(clean, noisy) + 3.0


def test_nmf_preserves_length_and_dtype():
    noisy, _ = synthetic_snore_scene(seconds=10.0)
    out = nmf_denoise(noisy, SR)
    assert out.shape == noisy.shape and out.dtype == np.float32


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
