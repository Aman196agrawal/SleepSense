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

_AUDIO_EXTS = (".m4a", ".wav", ".mp3", ".opus", ".flac")


def _candidate_sources():
    """Paths to try, in priority order, plus any audio found in a recordings dir."""
    here = os.path.dirname(os.path.abspath(__file__))
    explicit = os.environ.get("SNORE_PCEN_SRC")
    if explicit:
        yield explicit

    roots = []
    env_root = os.environ.get("SNORE_RECORDINGS")
    if env_root:
        roots.append(env_root)
    # Where the recordings actually live: <repo>/Recordings (gitignored, so the
    # multi-hundred-MB m4a files stay out of git).
    roots.append(os.path.abspath(os.path.join(here, "..", "Recordings")))
    # Also try the sibling-of-repo location that 03_denoise_explore.ipynb assumes,
    # in case a checkout keeps them outside the tree.
    roots.append(os.path.abspath(os.path.join(here, "..", "..", "Recordings")))

    for root in roots:
        if not os.path.isdir(root):
            continue
        for name in sorted(os.listdir(root)):
            if name.lower().endswith(_AUDIO_EXTS):
                yield os.path.join(root, name)


_PREFERRED_OFFSET = 3600.0   # an hour in — deep sleep, AC likely cycling
_SLICE_SEC = 60.0
_MIN_SEC = 10.0              # below this the contrast/sweep numbers are meaningless


def _load_usable(src: str):
    """Try the mid-night window, then fall back to the file start for shorter
    recordings. Returns (waveform, note) or (None, reason)."""
    for offset in (_PREFERRED_OFFSET, 0.0):
        try:
            y = D.load_slice(src, offset=offset, duration=_SLICE_SEC, sr=SR)
        except Exception as e:                      # noqa: BLE001 - report, don't crash
            return None, f"decode failed ({type(e).__name__}: {e})"
        if len(y) >= _MIN_SEC * SR:
            return y, f"{len(y) / SR:.0f}s window at offset {offset:.0f}s"
    return None, (f"yields under {_MIN_SEC:.0f}s of audio even from the start "
                  f"— needs a longer recording")


def _real_slice():
    """Returns (waveform, description) or (None, list of 'path -> reason')."""
    tried = []
    for src in _candidate_sources():
        if not os.path.exists(src):
            tried.append(f"{src}  ->  not found")
            continue
        y, note = _load_usable(src)
        if y is not None:
            return y, f"{src}  ({note})"
        tried.append(f"{src}  ->  {note}")
    return None, tried


def sweep_and_validate() -> bool:
    """Returns True only if the validation actually ran against real audio."""
    y, info = _real_slice()
    if y is None:
        print("\n" + "!" * 76)
        print("!! REAL-RECORDING VALIDATION DID NOT RUN — no source audio found.")
        print("!! The time_constant sweep did not execute, so the 'PCEN beats")
        print("!! log-mel' claim is UNVERIFIED in this environment.")
        if info:
            print("!! Tried:")
            for p in info:
                print(f"!!   {p}")
        else:
            print("!! No candidate paths existed to try.")
        print("!! Point at one with:  SNORE_PCEN_SRC=/path/to/recording.m4a")
        print("!! or a directory with: SNORE_RECORDINGS=/path/to/Recordings")
        print("!" * 76)
        return False
    print(f"\nvalidating against: {info}")
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
    return True


if __name__ == "__main__":
    test_shape_and_finite()
    test_deterministic()
    test_silent_and_short()
    validated = sweep_and_validate()

    if validated:
        print("\nALL CHECKS DONE (unit + real-recording validation)")
    else:
        # Do not claim "all checks done" when the headline claim was never tested.
        print("\nUNIT CHECKS PASSED — real-recording validation SKIPPED (see above)")
        if os.environ.get("SNORE_PCEN_REQUIRE_REAL"):
            print("SNORE_PCEN_REQUIRE_REAL is set — treating the skip as a failure.")
            sys.exit(1)
