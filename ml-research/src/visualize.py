"""
Visualization helpers for the snore-denoising feature.

Reusable, side-effect-free plotting functions (they take numpy arrays and return a
matplotlib Figure) used by notebooks/03_denoise_explore.ipynb and ad-hoc scripts.

The headline view is `raw_vs_clean` — two spectrograms (time × frequency, energy =
colour) stacked so the noise removed between snore bursts is immediately visible.
"""
from __future__ import annotations

import numpy as np
from scipy import signal

# A flat (non-gouraud) mesh with modest overlap keeps long (multi-minute) slices
# renderable without exhausting memory — gouraud + high overlap blows up fast.
_NPERSEG = 1024
_NOVERLAP = 512
_FMAX = 2000          # snore energy lives below ~2 kHz; crop for a readable view
_DB_FLOOR, _DB_CEIL = -110, -50


def _spectrogram_db(y: np.ndarray, sr: int):
    f, t, S = signal.spectrogram(y, sr, nperseg=_NPERSEG, noverlap=_NOVERLAP)
    return f, t, 10 * np.log10(S + 1e-12)


def draw_spectrogram(ax, y: np.ndarray, sr: int, title: str = "", fmax: int = _FMAX):
    """Draw one spectrogram onto an existing Axes. Returns the QuadMesh (for colorbars)."""
    f, t, Sdb = _spectrogram_db(y, sr)
    mesh = ax.pcolormesh(t, f, Sdb, shading="auto", cmap="magma",
                         vmin=_DB_FLOOR, vmax=_DB_CEIL)
    ax.set_ylim(0, fmax)
    ax.set_ylabel("Hz")
    ax.set_xlabel("s")
    if title:
        ax.set_title(title, fontsize=10)
    return mesh


def raw_vs_clean(raw: np.ndarray, clean: np.ndarray, sr: int,
                 raw_title: str = "RAW", clean_title: str = "CLEANED",
                 fmax: int = _FMAX):
    """Stacked raw-vs-clean spectrogram comparison. Returns a matplotlib Figure."""
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(2, 1, figsize=(14, 7), sharex=True)
    draw_spectrogram(ax[0], raw, sr, raw_title, fmax)
    mesh = draw_spectrogram(ax[1], clean, sr, clean_title, fmax)
    fig.colorbar(mesh, ax=ax, label="dB", pad=0.01)
    return fig


def presets_grid(raw: np.ndarray, cleaned: dict[str, np.ndarray], sr: int,
                 fmax: int = _FMAX):
    """One spectrogram row for RAW + each preset in `cleaned` (label -> waveform)."""
    import matplotlib.pyplot as plt
    rows = 1 + len(cleaned)
    fig, ax = plt.subplots(rows, 1, figsize=(14, 3 * rows), sharex=True)
    draw_spectrogram(ax[0], raw, sr, "RAW", fmax)
    for i, (label, y) in enumerate(cleaned.items(), start=1):
        draw_spectrogram(ax[i], y, sr, label, fmax)
    fig.tight_layout()
    return fig


def psd_compare(active: np.ndarray, noise: np.ndarray, sr: int,
                mains_hz: float = 50.0):
    """Welch-PSD overlay of an active (snore) slice vs a noise-floor slice, with
    a full-band view and a 0-300 Hz zoom on the snore-fundamental / AC-rumble region.
    Mains-hum harmonics are marked. Returns a Figure."""
    import matplotlib.pyplot as plt
    fa, Pa = signal.welch(active, sr, nperseg=4096)
    fn, Pn = signal.welch(noise, sr, nperseg=4096)
    fig, ax = plt.subplots(1, 2, figsize=(14, 5))
    for a, xlim, title in (
        (ax[0], (0, 2000), "Spectrum 0-2 kHz"),
        (ax[1], (0, 300), "Zoom 0-300 Hz (snore fundamental vs AC rumble)"),
    ):
        a.semilogy(fa, Pa, lw=0.8, label="active (snore+noise)")
        a.semilogy(fn, Pn, lw=0.8, alpha=0.8, label="noise floor")
        a.set_xlim(*xlim); a.set_xlabel("Hz"); a.set_ylabel("PSD")
        a.set_title(title); a.grid(alpha=0.3)
        for k in range(1, 4):
            a.axvline(mains_hz * k, color="r", ls=":", alpha=0.4)
    ax[0].legend()
    fig.tight_layout()
    return fig


def waveforms(raw: np.ndarray, clean: np.ndarray, sr: int):
    """Stacked raw/clean waveform envelopes on a shared time axis — the literal
    'amplitude over time, before vs after' view."""
    import matplotlib.pyplot as plt
    t = np.arange(len(raw)) / sr
    tc = np.arange(len(clean)) / sr
    fig, ax = plt.subplots(2, 1, figsize=(14, 5), sharex=True)
    ax[0].plot(t, raw, lw=0.4); ax[0].set_title("RAW", fontsize=10); ax[0].set_ylabel("amp")
    ax[1].plot(tc, clean, lw=0.4, color="C1"); ax[1].set_title("CLEANED", fontsize=10)
    ax[1].set_ylabel("amp"); ax[1].set_xlabel("s")
    fig.tight_layout()
    return fig


def band_energy_table(active: np.ndarray, noise: np.ndarray, sr: int) -> str:
    """Text table of per-band power (dB) for active vs noise + delta — quick SNR
    read-out for tuning. Returns a printable string."""
    fa, Pa = signal.welch(active, sr, nperseg=4096)
    fn, Pn = signal.welch(noise, sr, nperseg=4096)

    def band(f, P, lo, hi):
        m = (f >= lo) & (f < hi)
        return 10 * np.log10(P[m].mean() + 1e-12)

    bands = [(0, 50, "sub/rumble"), (50, 150, "AC band"), (150, 300, "snore-fund"),
             (300, 1000, "snore-harm"), (1000, 4000, "fan/hiss"), (4000, 8000, "hiss-hi")]
    lines = [f"{'band':12s} {'range':>10s}  {'active':>7s} {'noise':>7s} {'delta':>6s}"]
    for lo, hi, name in bands:
        A, N = band(fa, Pa, lo, hi), band(fn, Pn, lo, hi)
        lines.append(f"{name:12s} {f'{lo}-{hi}Hz':>10s}  {A:7.1f} {N:7.1f} {A-N:+6.1f}")
    return "\n".join(lines)
