"""
Unit + validation checks for src/pcen.py, plus the time_constant tuning sweep.

Run directly:  python test_pcen.py
Optionally point at a real recording for the validation/sweep:
  SNORE_PCEN_SRC="..../14 June recording papa.m4a" python test_pcen.py
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
import pcen as P  # noqa: E402
import denoise as D  # noqa: E402  (for load_slice on real audio)

SR = P.SAMPLE_RATE


# ── Unit tests (no real audio needed) ────────────────────────────────────────────

def test_shape_and_finite():
    y = np.sin(2 * np.pi * 100 * np.arange(SR * 3) / SR).astype(np.float32)
    M, t, f = P.pcen_spectrogram(y, SR)
    assert M.shape[0] == P.N_MELS, M.shape
    assert M.shape[1] == len(t), (M.shape, len(t))
    assert len(f) == P.N_MELS
    assert np.all(np.isfinite(M)), "PCEN produced non-finite values"
    print("ok  shape/finite", M.shape)


def test_deterministic():
    y = np.random.default_rng(0).standard_normal(SR * 2).astype(np.float32) * 0.1
    a, _, _ = P.pcen_spectrogram(y, SR)
    b, _, _ = P.pcen_spectrogram(y, SR)
    assert np.array_equal(a, b), "PCEN not deterministic"
    print("ok  deterministic")


def test_silent_and_short():
    silent = np.zeros(SR, dtype=np.float32)
    M, _, _ = P.pcen_spectrogram(silent, SR)
    assert np.all(np.isfinite(M)), "silent input -> non-finite"
    short = np.zeros(P.N_FFT // 2, dtype=np.float32)  # < one full frame
    Ms, _, _ = P.pcen_spectrogram(short, SR)
    assert np.all(np.isfinite(Ms)) and Ms.shape[0] == P.N_MELS
    print("ok  silent + very-short input")


# ── Validation + tuning (needs a real recording) ─────────────────────────────────

def _real_slice():
    src = os.environ.get(
        "SNORE_PCEN_SRC",
        r"C:/Users/BIT/OneDrive/Desktop/Nitu Chacha/Recordings/14 June recording papa.m4a")
    if not os.path.exists(src):
        return None
    return D.load_slice(src, offset=3600, duration=60, sr=SR)


def sweep_and_validate():
    y = _real_slice()
    if y is None:
        print("skip validation/sweep (no real recording found)")
        return
    fe = P.snore_frame_energy(y, SR)                       # shared activity reference
    S_db, _, _ = P.logmel_spectrogram(y, SR)
    base = P.active_gap_contrast(S_db, frame_energy=fe)
    print(f"\nlog-mel baseline contrast: {base:.3f}")
    print("time_constant sweep (PCEN active-vs-gap contrast, higher=snore pops more):")
    best = (None, -np.inf)
    for tc in (0.2, 0.4, 0.8, 1.5, 3.0):
        M, _, _ = P.pcen_spectrogram(y, SR, time_constant=tc)
        c = P.active_gap_contrast(M, frame_energy=fe)
        flag = ""
        if c > best[1]:
            best = (tc, c); flag = " <-- best so far"
        print(f"  tc={tc:>4} : contrast={c:6.3f}{flag}")
    print(f"\nBEST time_constant={best[0]} (contrast {best[1]:.3f}) vs log-mel {base:.3f}")
    assert best[1] > base, "PCEN should beat log-mel on snore-vs-background contrast"
    print("ok  PCEN beats log-mel contrast")
    print(f"current pcen.py default time_constant = {P.PCEN_TIME_CONSTANT}")


if __name__ == "__main__":
    test_shape_and_finite()
    test_deterministic()
    test_silent_and_short()
    sweep_and_validate()
    print("\nALL CHECKS DONE")
