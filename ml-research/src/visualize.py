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

# Mel-spectrogram params — kept in sync with src/features.py so the picture matches
# what the on-device CNN actually consumes.
_N_MELS, _MEL_NFFT, _MEL_HOP, _MEL_FMIN, _MEL_FMAX = 128, 1024, 512, 50, 8000


def _spectrogram_db(y: np.ndarray, sr: int):
    f, t, S = signal.spectrogram(y, sr, nperseg=_NPERSEG, noverlap=_NOVERLAP)
    return f, t, 10 * np.log10(S + 1e-12)


def _mel_power(y: np.ndarray, sr: int, fmax: int) -> np.ndarray:
    import librosa
    return librosa.feature.melspectrogram(y=y, sr=sr, n_fft=_MEL_NFFT, hop_length=_MEL_HOP,
                                          n_mels=_N_MELS, fmin=_MEL_FMIN, fmax=fmax)


def mel_peak(y: np.ndarray, sr: int, fmax: int = _MEL_FMAX) -> float:
    """Peak mel power of `y`, for use as a shared 0 dB reference across panels."""
    return float(_mel_power(y, sr, fmax).max())


def draw_mel_spectrogram(ax, y: np.ndarray, sr: int, title: str = "", fmax: int = _MEL_FMAX,
                         ref: float | None = None):
    """Draw a log-mel spectrogram (the CNN's input view) onto an existing Axes.
    Mel params mirror src/features.py. Returns the image (for colorbars).

    `ref` sets the 0 dB reference. Leave it None for a standalone panel; pass a
    shared value (see `mel_peak`) whenever two panels are meant to be compared,
    otherwise each is normalised to its own peak and level differences vanish."""
    import librosa
    import librosa.display
    S = librosa.feature.melspectrogram(y=y, sr=sr, n_fft=_MEL_NFFT, hop_length=_MEL_HOP,
                                       n_mels=_N_MELS, fmin=_MEL_FMIN, fmax=fmax)
    S_db = librosa.power_to_db(S, ref=np.max if ref is None else ref)
    img = librosa.display.specshow(S_db, sr=sr, hop_length=_MEL_HOP, x_axis="time",
                                   y_axis="mel", fmin=_MEL_FMIN, fmax=fmax, ax=ax,
                                   cmap="magma", vmin=-80, vmax=0)
    if title:
        ax.set_title(title, fontsize=10)
    return img


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
                 fmax: int | None = None, mel: bool = False):
    """Stacked raw-vs-clean comparison. mel=True draws log-mel (the CNN's view)
    instead of the linear STFT spectrogram. Returns a matplotlib Figure."""
    import matplotlib.pyplot as plt
    fm = fmax if fmax is not None else (_MEL_FMAX if mel else _FMAX)
    fig, ax = plt.subplots(2, 1, figsize=(14, 7), sharex=True)
    if mel:
        # Both panels share the raw signal's peak as 0 dB. Per-panel ref=np.max
        # would renormalise each one to its own peak, so a uniformly quieter
        # CLEANED signal would look identical to RAW — and the single colorbar
        # below would only ever be valid for the bottom panel.
        ref = mel_peak(raw, sr, fm)
        draw_mel_spectrogram(ax[0], raw, sr, raw_title, fm, ref=ref)
        img = draw_mel_spectrogram(ax[1], clean, sr, clean_title, fm, ref=ref)
    else:
        # The linear path is already on an absolute dB scale (_DB_FLOOR/_DB_CEIL).
        draw_spectrogram(ax[0], raw, sr, raw_title, fm)
        img = draw_spectrogram(ax[1], clean, sr, clean_title, fm)
    fig.colorbar(img, ax=ax, label="dB", pad=0.01)
    return fig


def draw_pcen(ax, M: np.ndarray, times: np.ndarray, freqs: np.ndarray, title: str = ""):
    """Draw a PCEN matrix (n_mels × n_frames) onto an existing Axes. PCEN is
    dimensionless (≈0–a few), so the colour scale auto-ranges. Returns the QuadMesh."""
    mesh = ax.pcolormesh(times, freqs, M, shading="auto", cmap="magma")
    ax.set_ylabel("Hz")
    ax.set_xlabel("s")
    if title:
        ax.set_title(title, fontsize=10)
    return mesh


def logmel_vs_pcen(y: np.ndarray, sr: int, fmax: float = 2000, title: str = ""):
    """Stacked log-mel (top) vs PCEN (bottom) for the same waveform — shows PCEN
    flattening the stationary AC/fan floor so the snore pops. Returns a Figure."""
    import matplotlib.pyplot as plt
    import pcen as P
    S_db, t0, f0 = P.logmel_spectrogram(y, sr, fmax=fmax)
    M, t1, f1 = P.pcen_spectrogram(y, sr, fmax=fmax)
    pre = f"{title} — " if title else ""
    fig, ax = plt.subplots(2, 1, figsize=(14, 7), sharex=True)
    im0 = ax[0].pcolormesh(t0, f0, S_db, shading="auto", cmap="magma", vmin=-80, vmax=0)
    ax[0].set_ylabel("Hz")
    ax[0].set_title(pre + "log-mel (dB)", fontsize=10)
    fig.colorbar(im0, ax=ax[0], pad=0.01)
    im1 = draw_pcen(ax[1], M, t1, f1, pre + "PCEN")
    fig.colorbar(im1, ax=ax[1], pad=0.01)
    return fig


def presets_grid(raw: np.ndarray, cleaned: dict[str, np.ndarray], sr: int,
                 fmax: int | None = None, mel: bool = False):
    """One spectrogram row for RAW + each preset in `cleaned` (label -> waveform).
    mel=True renders log-mel spectrograms (the CNN input view)."""
    import matplotlib.pyplot as plt
    fm = fmax if fmax is not None else (_MEL_FMAX if mel else _FMAX)
    rows = 1 + len(cleaned)
    fig, ax = plt.subplots(rows, 1, figsize=(14, 3 * rows), sharex=True)
    if mel:
        # Same shared-reference rule as raw_vs_clean — every preset row is scored
        # against the RAW peak, so rows are comparable to each other.
        ref = mel_peak(raw, sr, fm)
        draw_mel_spectrogram(ax[0], raw, sr, "RAW", fm, ref=ref)
        for i, (label, y) in enumerate(cleaned.items(), start=1):
            draw_mel_spectrogram(ax[i], y, sr, label, fm, ref=ref)
    else:
        draw_spectrogram(ax[0], raw, sr, "RAW", fm)
        for i, (label, y) in enumerate(cleaned.items(), start=1):
            draw_spectrogram(ax[i], y, sr, label, fm)
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
