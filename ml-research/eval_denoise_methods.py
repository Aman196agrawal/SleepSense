"""
Side-by-side evaluation of all denoise methods on a REAL night recording.

Scores each variant with the no-reference harness (src/metrics.py): active/gap
SNR, noise floor, snore-band retention, gap flatness (musical noise). The
synthetic-scene SI-SDR story lives in tests/test_denoise_methods.py; this is
the same methods on the real thing.

Usage:
    python eval_denoise_methods.py "../Recordings/14 June recording papa.m4a"
    python eval_denoise_methods.py SRC --offsets 3600 7200 10800 --duration 120
"""
from __future__ import annotations

import argparse
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
import denoise as D  # noqa: E402
import metrics as M  # noqa: E402


def pick_snoriest(path: str, offsets: list[float], duration: float):
    """Of the candidate offsets, keep the slice whose raw active/gap SNR is
    highest — i.e. the one that clearly contains snoring to preserve."""
    best = None
    for off in offsets:
        y = D.load_slice(path, offset=off, duration=duration)
        if not len(y):
            continue
        snr = M.waveform_metrics(y).snr_active_gap_db
        print(f"  offset {off/3600:.1f} h: active/gap SNR {snr:5.1f} dB")
        if best is None or snr > best[2]:
            best = (off, y, snr)
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--offsets", type=float, nargs="+", default=[3600, 7200, 10800])
    ap.add_argument("--duration", type=float, default=120.0)
    ap.add_argument("--deep", action="store_true", help="also run the DNS64 deep denoiser")
    ap.add_argument("--save", action="store_true", help="write each variant as a wav to output/method_eval/")
    a = ap.parse_args()

    print(f"[scan] choosing the snore-heaviest of {len(a.offsets)} slices ...")
    off, y, snr = pick_snoriest(a.src, a.offsets, a.duration)
    sr = D.SAMPLE_RATE
    print(f"[eval] using offset {off/3600:.2f} h ({a.duration:.0f} s, raw SNR {snr:.1f} dB)\n")

    import noisereduce as nr
    variants: dict[str, np.ndarray] = {"RAW": y}

    def run(name, fn):
        t0 = time.time()
        variants[name] = fn()
        print(f"  {name:<14s} {time.time()-t0:6.1f} s")

    # deep runs FIRST: loading torch after sklearn/noisereduce have initialised
    # their OpenMP runtimes segfaults on this machine (duplicate OpenMP).
    if a.deep:
        run("deep", lambda: D.denoise(y, sr, "deep"))

    run("old_global", lambda: nr.reduce_noise(
        y=y, sr=sr, stationary=True, y_noise=D._auto_noise_clip(y, sr),
        prop_decrease=0.9).astype(np.float32))
    run("safe", lambda: D.denoise(y, sr, "safe"))
    run("local_gap", lambda: D.multi_profile_denoise(y, sr, n_profiles=1))
    run("multi_k2", lambda: D.multi_profile_denoise(y, sr, n_profiles=2))
    run("mmse_lsa", lambda: D.mmse_lsa_denoise(y, sr))
    run("nmf", lambda: D.nmf_denoise(y, sr))
    # Level-match: peak-normalize every variant (incl. RAW) so the scale-
    # dependent columns (NoiseFl, SnoreBd) compare fairly — `safe` normalizes
    # internally while the others don't.
    for k, v in variants.items():
        peak = float(np.max(np.abs(v)))
        if peak > 1e-6:
            variants[k] = (v / peak * 0.97).astype(np.float32)

    if a.save:
        import soundfile as sf
        out_dir = os.path.join(os.path.dirname(__file__), "output", "method_eval")
        os.makedirs(out_dir, exist_ok=True)
        for k, v in variants.items():
            sf.write(os.path.join(out_dir, f"{off:.0f}s_{k}.wav"), v, sr)
        print(f"\n[save] wrote {len(variants)} wavs to {out_dir}")

    print()
    print(M.metrics_table(variants, sr))
    print("\nHigher is better: SNR, dSNR, NoiseRed, Flat. SnoreBd delta near 0 = snore preserved.")


if __name__ == "__main__":
    main()
