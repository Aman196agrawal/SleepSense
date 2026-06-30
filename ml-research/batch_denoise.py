"""
Batch-denoise a full multi-hour recording with a `denoise` preset.

Streams the source in overlapping chunks (overlap-save: edges are computed with
real context then discarded, so chunk seams are inaudible), uses ONE global noise
profile measured from the quietest segment of the whole night, and applies a
SINGLE global gain (per-chunk normalization would pump the level between chunks).

Usage:
    python batch_denoise.py "../Recordings/14 June recording papa.m4a" --preset safe
    python batch_denoise.py SRC --preset safe --out clean.wav --chunk 120 --ctx 3
"""
from __future__ import annotations

import argparse
import dataclasses
import os
import re
import subprocess
import sys
import time

import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
import denoise as D  # noqa: E402


def source_duration_s(path: str) -> float:
    import imageio_ffmpeg
    exe = imageio_ffmpeg.get_ffmpeg_exe()
    p = subprocess.run([exe, "-i", path], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", p.stderr)
    h, mn, s = m.groups()
    return int(h) * 3600 + int(mn) * 60 + float(s)


def scan_noise_and_peak(path: str, sr: int, total_s: float,
                        win_s: float = 2.0, block_s: float = 300.0):
    """One pass over the file: return (quietest `win_s` clip, global peak |x|).

    The quiet clip is the snore-free AC/fan floor → the stationary-subtraction
    noise fingerprint. The peak feeds the single global output gain.
    """
    w = int(sr * win_s)
    step = int(sr * 0.5)
    best_e, best_clip, peak = np.inf, None, 0.0
    t = 0.0
    while t < total_s:
        y = D.load_slice(path, offset=t, duration=min(block_s, total_s - t), sr=sr)
        if len(y):
            peak = max(peak, float(np.max(np.abs(y))))
        for s in range(0, max(0, len(y) - w), step):
            e = float(np.mean(y[s:s + w] ** 2))
            if e < best_e:
                best_e, best_clip = e, y[s:s + w].copy()
        t += block_s
    return best_clip, peak


def batch_denoise(path: str, out: str, preset: str = "safe", sr: int = D.SAMPLE_RATE,
                  chunk_s: float = 120.0, ctx_s: float = 3.0) -> None:
    cfg = dataclasses.replace(D.PRESETS[preset], normalize=False)  # global gain instead
    total_s = source_duration_s(path)
    total_n = int(total_s * sr)

    print(f"[scan] measuring noise profile + peak over {total_s/3600:.2f} h ...", flush=True)
    t0 = time.time()
    noise_clip, in_peak = scan_noise_and_peak(path, sr, total_s)
    g = 0.97 / max(in_peak, 1e-6)
    print(f"[scan] done in {time.time()-t0:.0f}s  (peak={in_peak:.3f}, gain={g:.3f})", flush=True)

    chunk, ctx = int(chunk_s * sr), int(ctx_s * sr)
    t1 = time.time()
    with sf.SoundFile(out, "w", samplerate=sr, channels=1, subtype="PCM_16") as w:
        pos = 0
        while pos < total_n:
            a = max(0, pos - ctx)
            b = min(total_n, pos + chunk + ctx)
            y = D.load_slice(path, offset=a / sr, duration=(b - a) / sr, sr=sr)
            clean = D.denoise(y, sr, cfg, noise_clip=noise_clip)
            s0 = pos - a
            keep_n = min(pos + chunk, total_n) - pos
            seg = clean[s0:s0 + keep_n]
            w.write(np.clip(seg * g, -1.0, 1.0).astype(np.float32))
            pos += chunk
            done = min(pos, total_n) / total_n
            print(f"[proc] {done*100:5.1f}%  ({pos/sr/3600:.2f}/{total_s/3600:.2f} h)  "
                  f"elapsed {time.time()-t1:.0f}s", flush=True)
    print(f"[done] wrote {out}  ({os.path.getsize(out)/1e6:.0f} MB) in "
          f"{time.time()-t1:.0f}s", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--preset", default="safe")
    ap.add_argument("--out", default=None)
    ap.add_argument("--chunk", type=float, default=120.0, help="chunk seconds")
    ap.add_argument("--ctx", type=float, default=3.0, help="overlap-save context seconds")
    a = ap.parse_args()
    out = a.out or os.path.join(
        "output", f"{os.path.splitext(os.path.basename(a.src))[0]}_{a.preset}.wav")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    batch_denoise(a.src, out, a.preset, chunk_s=a.chunk, ctx_s=a.ctx)
