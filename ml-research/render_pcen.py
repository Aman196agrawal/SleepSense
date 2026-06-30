"""
Render log-mel vs PCEN comparison figures for a real recording.

Decodes the source once to a contiguous wav (same path the cleaned files were made
with — avoids the ffmpeg `-ss` decode-drift) and renders the comparison at a few
offsets across the night so AC-on and AC-off stretches are both covered.

Usage:
  python render_pcen.py "../Recordings/14 June recording papa.m4a"
  python render_pcen.py SRC --offsets 600 3600 10800 --dur 60
"""
import argparse
import os
import sys

import numpy as np
import soundfile as sf
import matplotlib
matplotlib.use("Agg")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
import pcen as P  # noqa: E402
import visualize as V  # noqa: E402
import batch_denoise as B  # noqa: E402

SR = P.SAMPLE_RATE


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--offsets", type=float, nargs="+", default=[600, 3600, 7200],
                    help="window start times in seconds")
    ap.add_argument("--dur", type=float, default=60.0)
    ap.add_argument("--outdir", default="output/pcen")
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)

    tmp = os.path.join(a.outdir, "_decoded.wav")
    print("[decode] decoding source once (contiguous, sample-accurate) ...", flush=True)
    B.decode_to_wav(a.src, tmp, SR)
    try:
        total = sf.info(tmp).frames
        stem = os.path.splitext(os.path.basename(a.src))[0]
        for off in a.offsets:
            start = int(off * SR)
            if start + int(a.dur * SR) > total:
                print(f"  skip offset {off}s (past end)")
                continue
            with sf.SoundFile(tmp) as f:
                f.seek(start)
                y = f.read(int(a.dur * SR), dtype="float32")
            fe = P.snore_frame_energy(y, SR)
            S_db, _, _ = P.logmel_spectrogram(y, SR)
            M, _, _ = P.pcen_spectrogram(y, SR)
            c_log = P.active_gap_contrast(S_db, frame_energy=fe)
            c_pcen = P.active_gap_contrast(M, frame_energy=fe)
            hh = int(off // 3600); mm = int((off % 3600) // 60)
            fig = V.logmel_vs_pcen(y, SR, title=f"{stem}  {hh:02d}:{mm:02d}")
            op = os.path.join(a.outdir, f"{stem}_pcen_{int(off)}s.png")
            fig.savefig(op, dpi=120, bbox_inches="tight")
            import matplotlib.pyplot as plt
            plt.close(fig)
            print(f"[render] {off:>6.0f}s  contrast log-mel={c_log:.3f}  PCEN={c_pcen:.3f}  "
                  f"-> {op}", flush=True)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    print("[done]")


if __name__ == "__main__":
    main()
