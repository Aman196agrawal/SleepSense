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
        # An explicitly named file means "sweep exactly this one" — do not also
        # pull in everything from the recordings directories.
        yield explicit
        return

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


_OFFSETS = (1800.0, 3600.0, 7200.0, 10800.0)   # spread across the night
_SLICE_SEC = 60.0
_MIN_SEC = 10.0              # below this the contrast/sweep numbers are meaningless
_TIME_CONSTANTS = (0.2, 0.4, 0.8, 1.5, 3.0)

# A window where the loud and quiet frames barely differ contains no snoring to
# separate from background, so active_gap_contrast is scoring noise against
# noise. 6 dB between the 90th and 10th percentile of snore-band energy is a
# HEURISTIC chosen for this analysis, not a validated criterion — it is exposed
# so the sensitivity of the conclusions to it can be checked.
_MIN_ACTIVITY_DB = float(os.environ.get("SNORE_PCEN_MIN_ACTIVITY", "6.0"))


def _collect_windows():
    """Decode every (recording, offset) pair we can find.

    Returns (windows, tried) where windows is a list of dicts describing each
    usable slice, and tried explains anything that was rejected."""
    windows, tried = [], []
    seen = set()
    for src in _candidate_sources():
        # Normalise before de-duping: the same file reached via an env var and via
        # a directory scan differs in slash direction and case on Windows, which
        # previously let one recording be swept twice.
        canon = os.path.normcase(os.path.abspath(src))
        if canon in seen:
            continue
        seen.add(canon)
        if not os.path.exists(src):
            tried.append(f"{src}  ->  not found")
            continue
        got_any = False
        for off in _OFFSETS:
            try:
                y = D.load_slice(src, offset=off, duration=_SLICE_SEC, sr=SR)
            except Exception as e:                  # noqa: BLE001 - report, don't crash
                tried.append(f"{src} @{off:.0f}s  ->  decode failed "
                             f"({type(e).__name__}: {e})")
                continue
            if len(y) < _MIN_SEC * SR:
                continue                            # past the end of the file
            fe = P.snore_frame_energy(y, SR)
            spread = float(np.percentile(fe, 90) - np.percentile(fe, 10))
            windows.append({
                "src": os.path.basename(src), "offset": off,
                "y": y, "fe": fe, "spread": spread,
                "live": spread >= _MIN_ACTIVITY_DB,
            })
            got_any = True
        if not got_any:
            tried.append(f"{src}  ->  no window of >={_MIN_SEC:.0f}s at any offset")
    return windows, tried


def _no_audio_banner(tried):
    print("\n" + "!" * 76)
    print("!! REAL-RECORDING VALIDATION DID NOT RUN — no usable source audio.")
    print("!! The time_constant sweep did not execute, so the 'PCEN beats")
    print("!! log-mel' claim is UNVERIFIED in this environment.")
    if tried:
        print("!! Tried:")
        for p in tried:
            print(f"!!   {p}")
    else:
        print("!! No candidate paths existed to try.")
    print("!! Point at one with:  SNORE_PCEN_SRC=/path/to/recording.m4a")
    print("!! or a directory with: SNORE_RECORDINGS=/path/to/Recordings")
    print("!" * 76)


def sweep_and_validate() -> bool:
    """Multi-window time_constant sweep.

    Scores every time_constant on every live window, then picks the winner by
    MEDIAN RANK rather than by the single best score. One window's peak is what
    produced the previous default, and it did not generalise; median rank asks
    which setting is consistently good instead of exceptionally good once.

    Returns True only if the sweep actually ran against real audio."""
    windows, tried = _collect_windows()
    if not windows:
        _no_audio_banner(tried)
        return False

    live = [w for w in windows if w["live"]]
    print(f"\ndecoded {len(windows)} window(s); {len(live)} with >= "
          f"{_MIN_ACTIVITY_DB:.0f} dB active-gap spread (the rest are silent stretches)")
    if not live:
        print("\n" + "!" * 76)
        print("!! Every window is below the activity threshold — nothing to tune on.")
        print(f"!! Lower it with SNORE_PCEN_MIN_ACTIVITY (currently {_MIN_ACTIVITY_DB:.1f} dB)")
        print("!! if you believe these recordings do contain snoring.")
        print("!" * 76)
        return False

    # Score every tc on every live window, against a shared per-window activity
    # reference so PCEN and log-mel are judged on the same active/gap frames.
    print(f"\n{'recording':28s} {'off':>6s} {'spread':>7s} {'log-mel':>8s}  " +
          "  ".join(f"tc={tc:<4}" for tc in _TIME_CONSTANTS))
    print("-" * (52 + 8 * len(_TIME_CONSTANTS)))

    ranks = {tc: [] for tc in _TIME_CONSTANTS}
    pcen_wins = 0
    for w in live:
        S_db, _, _ = P.logmel_spectrogram(w["y"], SR)
        base = P.active_gap_contrast(S_db, frame_energy=w["fe"])
        scores = {}
        for tc in _TIME_CONSTANTS:
            M, _, _ = P.pcen_spectrogram(w["y"], SR, time_constant=tc)
            scores[tc] = P.active_gap_contrast(M, frame_energy=w["fe"])
        # Rank 1 = best on this window.
        order = sorted(_TIME_CONSTANTS, key=lambda t: scores[t], reverse=True)
        for pos, tc in enumerate(order, start=1):
            ranks[tc].append(pos)
        if max(scores.values()) > base:
            pcen_wins += 1
        print(f"{w['src'][:28]:28s} {w['offset']:6.0f} {w['spread']:7.1f} {base:8.3f}  " +
              "  ".join(f"{scores[tc]:6.3f}" for tc in _TIME_CONSTANTS))

    # Median rank, tie-broken by mean rank then by the smaller time_constant.
    def key(tc):
        return (float(np.median(ranks[tc])), float(np.mean(ranks[tc])), tc)

    ordered = sorted(_TIME_CONSTANTS, key=key)
    winner = ordered[0]

    print("\nmedian rank across live windows (1 = best; lower is better):")
    for tc in ordered:
        med, mean, _ = key(tc)
        mark = "  <-- most consistent" if tc == winner else ""
        print(f"  tc={tc:>4} : median={med:4.1f}  mean={mean:4.1f}  "
              f"ranks={ranks[tc]}{mark}")

    print(f"\nPCEN beat log-mel on {pcen_wins}/{len(live)} live window(s)")
    print(f"median-rank winner : time_constant={winner}")
    print(f"pcen.py default    : time_constant={P.PCEN_TIME_CONSTANT}")

    # These are research findings, not code defects, so they are surfaced loudly
    # rather than asserted — set SNORE_PCEN_STRICT=1 to enforce them once the
    # tuning is settled.
    problems = []
    if pcen_wins * 2 <= len(live):
        problems.append(f"PCEN loses to log-mel on most live windows "
                        f"({pcen_wins}/{len(live)}) — the documented advantage "
                        f"does not generalise")
    if winner != P.PCEN_TIME_CONSTANT:
        problems.append(f"pcen.py default ({P.PCEN_TIME_CONSTANT}) is not the "
                        f"most consistent setting ({winner})")
    if problems:
        print("\n" + "!" * 76)
        for p in problems:
            print(f"!! {p}")
        print("!! Set SNORE_PCEN_STRICT=1 to make these a hard failure.")
        print("!" * 76)
        if os.environ.get("SNORE_PCEN_STRICT"):
            sys.exit(1)
    else:
        print("ok  PCEN beats log-mel on a majority of windows at the configured default")

    # What must always hold: the sweep produced usable numbers.
    for tc in _TIME_CONSTANTS:
        assert len(ranks[tc]) == len(live), f"tc={tc} was not scored on every window"
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
