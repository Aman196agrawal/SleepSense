"""
Full-corpus PCEN time_constant sweep.

Samples every recording at a fixed interval across its whole duration, screens
out silent stretches, and scores each candidate time_constant on every window
that actually contains snoring.

Two independent metrics are computed so the choice does not rest on one
possibly-flawed score:

  contrast : active_gap_contrast from src/pcen.py — mean(z) over active frames
             minus mean(z) over gap frames, in std units of the representation.
  auc      : rank AUC of separating active from gap frames using the per-frame
             mean of the representation. Scale- and monotone-invariant, so it
             cannot be gamed by the compression PCEN applies. 0.5 = no
             separation, 1.0 = perfect.

Both are computed against the SAME activity reference (snore-band RMS), so
log-mel and every PCEN setting are judged on identical active/gap frames.

Usage:
  python sweep_pcen.py                      # 10-minute stride, full corpus
  python sweep_pcen.py --step-minutes 5
  python sweep_pcen.py --limit 2            # first N recordings only
"""
from __future__ import annotations

import argparse
import csv
import os
import subprocess
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
import pcen as P        # noqa: E402
import denoise as D     # noqa: E402
import librosa          # noqa: E402

SR = P.SAMPLE_RATE
AUDIO_EXTS = (".m4a", ".wav", ".mp3", ".opus", ".flac")
TIME_CONSTANTS = (0.1, 0.2, 0.3, 0.5, 0.8, 1.2, 1.6, 2.2, 3.0, 4.0)


# ── Corpus ───────────────────────────────────────────────────────────────────

def duration_seconds(path: str) -> float:
    """Duration via the bundled ffmpeg (imageio-ffmpeg ships no ffprobe)."""
    r = subprocess.run([D._ffmpeg_exe(), "-i", path],
                       capture_output=True, text=True, errors="ignore")
    for line in r.stderr.splitlines():
        if "Duration:" in line:
            hms = line.split("Duration:")[1].split(",")[0].strip()
            h, m, s = hms.split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    return 0.0


def recordings(root: str, limit: int | None):
    files = [os.path.join(root, f) for f in sorted(os.listdir(root))
             if f.lower().endswith(AUDIO_EXTS)]
    return files[:limit] if limit else files


# ── Metrics ──────────────────────────────────────────────────────────────────

def rank_auc(values: np.ndarray, positive: np.ndarray, negative: np.ndarray) -> float:
    """AUC of separating `positive` from `negative` frames, via rank statistics."""
    pos, neg = values[positive], values[negative]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    ranks = np.argsort(np.argsort(np.concatenate([pos, neg]))) + 1
    r_pos = ranks[:len(pos)].sum()
    return float((r_pos - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def score_matrix(M: np.ndarray, fe: np.ndarray, active: np.ndarray, gap: np.ndarray):
    """(contrast, auc) for one representation against a shared activity mask."""
    contrast = P.active_gap_contrast(M, frame_energy=fe)
    n = min(M.shape[1], len(fe))
    auc = rank_auc(M[:, :n].mean(axis=0), active[:n], gap[:n])
    return contrast, auc


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--recordings", default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "Recordings"))
    ap.add_argument("--step-minutes", type=float, default=10.0)
    ap.add_argument("--dur", type=float, default=60.0)
    ap.add_argument("--min-activity-db", type=float, default=6.0)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--outdir", default="output/pcen_sweep")
    a = ap.parse_args()

    root = os.path.abspath(a.recordings)
    os.makedirs(a.outdir, exist_ok=True)
    files = recordings(root, a.limit)
    if not files:
        print(f"no audio found in {root}")
        return 1

    print(f"corpus: {root}")
    total_h = 0.0
    plan = []
    for f in files:
        dur = duration_seconds(f)
        total_h += dur / 3600
        offs = np.arange(a.step_minutes * 60, dur - a.dur, a.step_minutes * 60)
        plan.append((f, offs))
        print(f"  {os.path.basename(f):32s} {dur/3600:5.2f} h  -> {len(offs)} windows")
    n_planned = sum(len(o) for _, o in plan)
    print(f"total {total_h:.2f} h, {n_planned} windows of {a.dur:.0f}s "
          f"at {a.step_minutes:.0f}-minute stride\n")

    rows = []
    t0 = time.time()
    done = 0
    for path, offs in plan:
        name = os.path.basename(path)
        for off in offs:
            done += 1
            y = D.load_slice(path, offset=float(off), duration=a.dur, sr=SR)
            if len(y) < 10 * SR:
                continue
            fe = P.snore_frame_energy(y, SR)
            spread = float(np.percentile(fe, 90) - np.percentile(fe, 10))
            active = fe >= np.percentile(fe, 90)
            gap = fe <= np.percentile(fe, 10)

            row = {"recording": name, "offset_s": int(off), "spread_db": round(spread, 2)}

            # Mel power computed ONCE and reused across time_constants — the
            # per-tc call in pcen_spectrogram would recompute it identically.
            S = P._mel_power(y, SR, P.VIZ_FMAX)
            S_db = librosa.power_to_db(S, ref=np.max)
            c, u = score_matrix(S_db, fe, active, gap)
            row["logmel_contrast"], row["logmel_auc"] = round(c, 4), round(u, 4)

            for tc in TIME_CONSTANTS:
                M = librosa.pcen(S * P.PCEN_INPUT_SCALE, sr=SR,
                                 hop_length=P.HOP_LENGTH, gain=P.PCEN_GAIN,
                                 bias=P.PCEN_BIAS, power=P.PCEN_POWER,
                                 time_constant=tc, eps=P.PCEN_EPS)
                c, u = score_matrix(M.astype(np.float32), fe, active, gap)
                row[f"c_{tc}"], row[f"a_{tc}"] = round(c, 4), round(u, 4)

            rows.append(row)
            if done % 10 == 0 or done == n_planned:
                el = time.time() - t0
                print(f"  [{done:3d}/{n_planned}] {el:5.0f}s elapsed "
                      f"({el/max(done,1):.1f}s/window)", flush=True)

    csv_path = os.path.join(a.outdir, "sweep.csv")
    with open(csv_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\nwrote {csv_path}  ({len(rows)} windows)\n")

    report(rows, a.min_activity_db)
    return 0


def report(rows, min_activity_db: float):
    def summarise(live, label):
        if not live:
            print(f"\n{label}: no windows")
            return None
        print(f"\n{'=' * 78}\n{label}  (n={len(live)})\n{'=' * 78}")
        out = {}
        for metric, prefix, base_key in (("contrast", "c_", "logmel_contrast"),
                                         ("auc", "a_", "logmel_auc")):
            ranks = {tc: [] for tc in TIME_CONSTANTS}
            wins = 0
            for r in live:
                scored = {tc: r[f"{prefix}{tc}"] for tc in TIME_CONSTANTS}
                order = sorted(TIME_CONSTANTS, key=lambda t: scored[t], reverse=True)
                for pos, tc in enumerate(order, 1):
                    ranks[tc].append(pos)
                if max(scored.values()) > r[base_key]:
                    wins += 1

            def key(tc):
                return (float(np.median(ranks[tc])), float(np.mean(ranks[tc])), tc)

            ordered = sorted(TIME_CONSTANTS, key=key)
            print(f"\n  by {metric}:   PCEN beats log-mel on {wins}/{len(live)} windows")
            print(f"  {'tc':>5} {'median':>7} {'mean':>6} {'top-3 %':>8}")
            for tc in ordered:
                med, mean, _ = key(tc)
                top3 = 100 * np.mean([p <= 3 for p in ranks[tc]])
                star = "  <--" if tc == ordered[0] else ""
                print(f"  {tc:>5} {med:7.1f} {mean:6.2f} {top3:7.0f}%{star}")
            out[metric] = ordered[0]
        return out

    live = [r for r in rows if r["spread_db"] >= min_activity_db]
    winners = summarise(live, f"ALL RECORDINGS, spread >= {min_activity_db} dB")

    # Per-recording, to check the choice is not driven by one file.
    for name in sorted({r["recording"] for r in rows}):
        sub = [r for r in live if r["recording"] == name]
        summarise(sub, f"{name}, spread >= {min_activity_db} dB")

    # Sensitivity to the (arbitrary) activity threshold.
    print(f"\n{'=' * 78}\nSENSITIVITY TO THE ACTIVITY THRESHOLD\n{'=' * 78}")
    print(f"  {'thresh':>7} {'n':>5} {'best by contrast':>18} {'best by auc':>13} "
          f"{'PCEN wins (auc)':>17}")
    for th in (0.0, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0):
        sub = [r for r in rows if r["spread_db"] >= th]
        if not sub:
            continue
        picks, wins = {}, 0
        for metric, prefix, base_key in (("contrast", "c_", "logmel_contrast"),
                                         ("auc", "a_", "logmel_auc")):
            ranks = {tc: [] for tc in TIME_CONSTANTS}
            w = 0
            for r in sub:
                scored = {tc: r[f"{prefix}{tc}"] for tc in TIME_CONSTANTS}
                for pos, tc in enumerate(sorted(TIME_CONSTANTS,
                                                key=lambda t: scored[t], reverse=True), 1):
                    ranks[tc].append(pos)
                if max(scored.values()) > r[base_key]:
                    w += 1
            picks[metric] = min(TIME_CONSTANTS,
                                key=lambda tc: (np.median(ranks[tc]), np.mean(ranks[tc]), tc))
            if metric == "auc":
                wins = w
        print(f"  {th:7.1f} {len(sub):5d} {picks['contrast']:18} {picks['auc']:13} "
              f"{wins:>10}/{len(sub)}")

    if winners:
        print(f"\nconfigured pcen.py default: time_constant={P.PCEN_TIME_CONSTANT}")


if __name__ == "__main__":
    sys.exit(main())
