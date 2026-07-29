"""
Produce a before/after denoising demo from the loudest real snore windows.

Picks the most active windows out of a sweep_pcen.py CSV (or an explicit
offset), decodes each one, runs the denoise presets over it, and writes
listenable WAVs plus a shared-scale spectrogram figure and a metrics table.

Usage:
  python make_demo_clip.py                        # top window from the sweep CSV
  python make_demo_clip.py --top 3
  python make_demo_clip.py --src REC.m4a --offset 4200
  python make_demo_clip.py --with-deep            # also run the torch DNS presets
"""
from __future__ import annotations

import argparse
import csv
import os
import sys

import numpy as np
import soundfile as sf
import matplotlib
matplotlib.use("Agg")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "src"))
import pcen as P        # noqa: E402
import denoise as D     # noqa: E402
import visualize as V   # noqa: E402
import metrics as MX    # noqa: E402

SR = P.SAMPLE_RATE
# "safe" first — it is the preset designed never to break the snore envelope,
# which is the one worth leading a demo with.
DEFAULT_PRESETS = ("safe", "gentle", "medium", "aggressive")
DEEP_PRESETS = ("deep", "deep_clean")


def pick_windows(csv_path: str, top: int):
    with open(csv_path, newline="") as fh:
        rows = list(csv.DictReader(fh))
    rows.sort(key=lambda r: float(r["spread_db"]), reverse=True)
    return [(r["recording"], float(r["offset_s"]), float(r["spread_db"]))
            for r in rows[:top]]


def normalise(y: np.ndarray, peak: float = 0.89) -> np.ndarray:
    """Scale to a fixed peak so presets are compared at equal loudness by ear.

    Denoising lowers absolute level, and a quieter file is easy to mistake for a
    cleaner one. Peak-matching removes that illusion — the WAVs differ only in
    what was removed, not how loud they are.
    """
    m = float(np.max(np.abs(y)))
    return (y * (peak / m)).astype(np.float32) if m > 0 else y.astype(np.float32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=os.path.join(HERE, "output/pcen_sweep/sweep.csv"))
    ap.add_argument("--recordings", default=os.path.join(HERE, "..", "Recordings"))
    ap.add_argument("--src", default=None, help="bypass the CSV; use this file")
    ap.add_argument("--offset", type=float, default=None)
    ap.add_argument("--dur", type=float, default=30.0)
    ap.add_argument("--top", type=int, default=1)
    ap.add_argument("--with-deep", action="store_true")
    ap.add_argument("--outdir", default=os.path.join(HERE, "output/demo"))
    a = ap.parse_args()

    root = os.path.abspath(a.recordings)
    os.makedirs(a.outdir, exist_ok=True)

    if a.src:
        picks = [(os.path.basename(a.src), a.offset or 0.0, float("nan"))]
        root = os.path.dirname(os.path.abspath(a.src)) or root
    else:
        if not os.path.exists(a.csv):
            print(f"no sweep CSV at {a.csv} — run sweep_pcen.py first, "
                  f"or pass --src/--offset")
            return 1
        picks = pick_windows(a.csv, a.top)

    presets = list(DEFAULT_PRESETS) + (list(DEEP_PRESETS) if a.with_deep else [])
    print(f"presets: {', '.join(presets)}\n")

    for rank, (name, off, spread) in enumerate(picks, 1):
        src = os.path.join(root, name)
        stem = f"{os.path.splitext(name)[0].replace(' ', '_')}_{int(off)}s"
        hh, mm = int(off // 3600), int((off % 3600) // 60)
        print(f"{'=' * 74}")
        print(f"[{rank}/{len(picks)}] {name}  @ {hh:02d}:{mm:02d} ({int(off)}s)"
              + (f"   active-gap spread {spread:.1f} dB" if spread == spread else ""))
        print(f"{'=' * 74}")

        raw = D.load_slice(src, offset=off, duration=a.dur, sr=SR)
        if len(raw) < 5 * SR:
            print("  window too short, skipping")
            continue

        # A quiet stretch from the SAME window is the noise fingerprint the
        # stationary presets subtract.
        noise = D._auto_noise_clip(raw, SR, seconds=2.0)

        variants = {"RAW": raw}
        for p in presets:
            try:
                variants[p] = D.denoise(raw, SR, p, noise_clip=noise)
                print(f"  ok  {p}")
            except Exception as e:                  # noqa: BLE001
                print(f"  !!  {p} failed: {type(e).__name__}: {e}")

        # WAVs, peak-matched so louder != cleaner.
        for label, y in variants.items():
            path = os.path.join(a.outdir, f"{stem}__{label}.wav")
            sf.write(path, normalise(y), SR)
        print(f"\n  wrote {len(variants)} WAVs to {a.outdir}")

        # Figures: headline before/after, then every preset stacked.
        lead = "safe" if "safe" in variants else presets[0]
        fig = V.raw_vs_clean(raw, variants[lead], SR,
                             raw_title=f"RAW — {name} @ {hh:02d}:{mm:02d}",
                             clean_title=f"CLEANED ({lead})")
        fig.savefig(os.path.join(a.outdir, f"{stem}__before_after.png"),
                    dpi=130, bbox_inches="tight")

        grid = V.presets_grid(raw, {k: v for k, v in variants.items() if k != "RAW"}, SR)
        grid.savefig(os.path.join(a.outdir, f"{stem}__all_presets.png"),
                     dpi=110, bbox_inches="tight")

        wave = V.waveforms(raw, variants[lead], SR)
        wave.savefig(os.path.join(a.outdir, f"{stem}__waveforms.png"),
                     dpi=110, bbox_inches="tight")
        print(f"  wrote 3 figures")

        table = MX.metrics_table(variants, SR, baseline="RAW")
        print(f"\n{table}\n")
        with open(os.path.join(a.outdir, f"{stem}__metrics.txt"), "w") as fh:
            fh.write(f"{name} @ {int(off)}s ({a.dur:.0f}s window)\n\n{table}\n")

    print(f"\nall output in {a.outdir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
