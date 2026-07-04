"""
Snore-recording denoiser (SleepSense graph-plotting feature).

Cleans night-time recordings made with a phone voice recorder where the sleeper
has an AC cycling on/off (non-stationary low-freq rumble + ~50 Hz mains hum) and a
fan running (stationary broadband hiss), so the snore becomes clearly audible and
usable for visualization / dataset building.

Tuned against real recordings in ../Recordings (AAC mono, 48 kHz, 4-6 h):
  - snore fundamental ~80-100 Hz, harmonics to ~1-2 kHz
  - noise floor sits ~15-20 dB below the snore in its core bands (good SNR)
  - mains hum near 50 Hz; sub-AC rumble below ~50 Hz

Source m4a/AAC is decoded with the ffmpeg binary bundled by `imageio-ffmpeg`
(no system ffmpeg required).

Presets
-------
  gentle     — classical (noisereduce); light touch; safest for ML training audio
  medium     — classical; balanced; good default
  aggressive — classical; maximum spectral-subtraction removal + gate
  deep       — learned DNS denoiser (Meta `denoiser`); biggest noise drop while
               PRESERVING the snore band, near-zero musical noise. Best quality.
  deep_clean — `deep` + envelope gate; best for human listening / visualization

The `deep` presets beat the classical ones by a wide margin on the metrics
harness (see src/metrics.py): ~60 dB noise-floor reduction with the snore band
left intact, vs noisereduce which erodes the snore as it cleans harder.
"""
from __future__ import annotations

import io
import subprocess
from dataclasses import dataclass

import numpy as np
import soundfile as sf
from scipy import signal

SAMPLE_RATE = 16_000   # matches the on-device model pipeline (see src/features.py)


# ── Decoding ────────────────────────────────────────────────────────────────────

def _ffmpeg_exe() -> str:
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def load_slice(path: str, offset: float = 0.0, duration: float | None = None,
               sr: int = SAMPLE_RATE) -> np.ndarray:
    """Decode a mono slice of any ffmpeg-readable file (incl. m4a/AAC) to float32.

    offset/duration in seconds; duration=None reads to end (use with care on
    multi-hour files — prefer bounded slices)."""
    cmd = [_ffmpeg_exe()]
    if offset:
        cmd += ["-ss", str(offset)]
    if duration is not None:
        cmd += ["-t", str(duration)]
    cmd += ["-i", path, "-ac", "1", "-ar", str(sr), "-f", "wav", "-loglevel", "error", "pipe:1"]
    raw = subprocess.run(cmd, capture_output=True).stdout
    y, _ = sf.read(io.BytesIO(raw))
    return y.astype(np.float32)


# ── Filter stages ───────────────────────────────────────────────────────────────

def highpass(y: np.ndarray, sr: int, cutoff_hz: float, order: int = 4) -> np.ndarray:
    """Butterworth high-pass — removes DC + sub-bass AC rumble below the snore
    fundamental. Zero-phase (filtfilt) so the snore waveform isn't time-shifted."""
    sos = signal.butter(order, cutoff_hz, btype="highpass", fs=sr, output="sos")
    return signal.sosfiltfilt(sos, y).astype(np.float32)


def notch_mains(y: np.ndarray, sr: int, freq_hz: float = 50.0, q: float = 30.0,
                harmonics: int = 3) -> np.ndarray:
    """Notch out mains hum and its harmonics (50 Hz + 100/150 Hz)."""
    out = y
    for k in range(1, harmonics + 1):
        f0 = freq_hz * k
        if f0 >= sr / 2:
            break
        b, a = signal.iirnotch(f0, q, fs=sr)
        out = signal.filtfilt(b, a, out)
    return out.astype(np.float32)


def spectral_denoise(y: np.ndarray, sr: int, noise_clip: np.ndarray | None,
                     stationary: bool, prop_decrease: float) -> np.ndarray:
    """Adaptive spectral noise reduction (Sainburg's `noisereduce`).

    stationary=True with a measured `noise_clip` subtracts a fixed fan/room
    fingerprint; stationary=False tracks the time-varying AC floor (AC on/off)."""
    import noisereduce as nr
    kwargs = dict(y=y, sr=sr, stationary=stationary, prop_decrease=prop_decrease)
    if noise_clip is not None and stationary:
        kwargs["y_noise"] = noise_clip
    return nr.reduce_noise(**kwargs).astype(np.float32)


# ── Deep-learning denoiser (Meta DNS / Demucs) ───────────────────────────────────

_DL_MODEL = None     # module-level cache — the 128 MB checkpoint loads once per process


def _load_dl_model():
    """Lazy-load + cache Meta's pretrained DNS64 denoiser (facebook `denoiser`).

    Installed without its training deps:  pip install --no-deps denoiser julius
    (the hydra/omegaconf pins it lists are 2019-era and break on modern Python;
    they are only needed for training, not inference). First call downloads the
    checkpoint to the torch hub cache."""
    global _DL_MODEL
    if _DL_MODEL is None:
        from denoiser.pretrained import dns64
        m = dns64()
        m.eval()
        _DL_MODEL = m
    return _DL_MODEL


def dl_denoise(y: np.ndarray, sr: int, dry: float = 0.0) -> np.ndarray:
    """Run a learned DNS denoiser (Demucs, 16 kHz mono).

    Unlike spectral subtraction this leaves almost no musical noise and — crucially
    for us — *preserves the snore band* while flattening the fan/AC floor (verified
    against the metrics harness). Feed it audio WITHOUT a mains-harmonic notch: a
    50 Hz-harmonic notch lands on the snore fundamental/harmonics and guts it.

    `dry` (0-1) mixes back some of the input to soften artifacts (0 = fully wet).
    """
    import torch
    model = _load_dl_model()
    model_sr = int(getattr(model, "sample_rate", 16_000))
    x = y
    if sr != model_sr:
        import librosa
        x = librosa.resample(x, orig_sr=sr, target_sr=model_sr)
    with torch.no_grad():
        t = torch.from_numpy(np.ascontiguousarray(x)).float()[None, None, :]
        est = model(t)[0, 0].cpu().numpy()
    if dry > 0:
        est = (1 - dry) * est + dry * x[: len(est)]
    if sr != model_sr:
        import librosa
        est = librosa.resample(est, orig_sr=model_sr, target_sr=sr)
    return est.astype(np.float32)


def noise_gate(y: np.ndarray, sr: int, threshold_db: float = -45.0,
               attack_ms: float = 10.0, release_ms: float = 150.0,
               floor_db: float = -25.0) -> np.ndarray:
    """Smooth envelope gate that ducks (not hard-mutes) quiet gaps between snores
    so the snores 'pop'. Keyed on the broadband envelope."""
    env = np.abs(signal.hilbert(y))
    # Smooth the control envelope
    win = max(1, int(sr * 0.02))
    env = np.convolve(env, np.ones(win) / win, mode="same")
    env_db = 20 * np.log10(env + 1e-9)
    target = np.where(env_db > threshold_db, 0.0, floor_db)  # dB of gain to apply
    # One-pole attack/release smoothing of the gain in dB
    a_att = np.exp(-1.0 / (sr * attack_ms / 1000.0))
    a_rel = np.exp(-1.0 / (sr * release_ms / 1000.0))
    gain = np.empty_like(target)
    g = 0.0
    for i, t in enumerate(target):
        coeff = a_att if t < g else a_rel
        g = coeff * g + (1 - coeff) * t
        gain[i] = g
    return (y * 10 ** (gain / 20.0)).astype(np.float32)


# ── Presets + pipeline ──────────────────────────────────────────────────────────

@dataclass
class DenoiseConfig:
    highpass_hz: float = 65.0
    notch: bool = True
    notch_freq: float = 50.0
    stationary: bool = True
    prop_decrease: float = 0.85
    gate: bool = False
    gate_threshold_db: float = -45.0
    normalize: bool = True
    use_dl: bool = False        # use the learned DNS denoiser instead of noisereduce
    dl_dry: float = 0.0         # dry/wet mix for the DL stage (0 = fully denoised)
    # Multiband non-breaking path (overrides the linear chain when set). Cleans the
    # out-of-band noise HARD and the in-band snore region GENTLY, so the snore
    # envelope is never modulated → no "breaking". See multiband_denoise().
    use_multiband: bool = False
    xover_hz: float = 1400.0    # snore band is 80-xover_hz; above it = fan hiss
    inband_prop: float = 0.65   # gentle subtraction inside the snore band (no breaking)
    outband_prop: float = 0.97  # hard subtraction outside it (no snore there to break)


PRESETS = {
    "gentle":     DenoiseConfig(highpass_hz=60, prop_decrease=0.6, stationary=True,  gate=False),
    "medium":     DenoiseConfig(highpass_hz=65, prop_decrease=0.85, stationary=False, gate=False),
    "aggressive": DenoiseConfig(highpass_hz=70, prop_decrease=0.95, stationary=False, gate=True,
                                gate_threshold_db=-42.0),
    # Deep presets: learned DNS denoiser. Only a *gentle* sub-bass highpass (well
    # below the ~80 Hz snore fundamental) and NO mains-harmonic notch — the model
    # handles the AC/fan floor and the notch would gut the snore harmonics.
    "deep":       DenoiseConfig(highpass_hz=40, notch=False, use_dl=True, gate=False),
    "deep_clean": DenoiseConfig(highpass_hz=40, notch=False, use_dl=True, gate=True,
                                gate_threshold_db=-45.0),
    # Non-breaking cleaner: hard on the rumble/hiss around the snore, gentle on the
    # snore band itself so its envelope is never modulated. The honest middle ground
    # when "the snore must NOT break" is the hard requirement. ~12 dB more hiss
    # reduction than `gentle` at 0% snore breaking (verified via the envelope-holes
    # metric). Stationary subtraction only — no gate, no DL, no time-varying gain.
    "safe":       DenoiseConfig(highpass_hz=70, notch=False, use_multiband=True,
                                xover_hz=1400.0, inband_prop=0.65, outband_prop=0.97),
}


def _auto_noise_clip(y: np.ndarray, sr: int, seconds: float = 2.0) -> np.ndarray:
    """Pick the quietest `seconds`-long window as a snore-free noise fingerprint for
    stationary spectral subtraction (the AC/fan floor between snores)."""
    win = int(sr * seconds)
    if len(y) <= win:
        return y
    step = max(1, int(sr * 0.5))
    energies = [(np.mean(y[s:s + win] ** 2), s) for s in range(0, len(y) - win, step)]
    _, s = min(energies)
    return y[s:s + win]


def _split(y: np.ndarray, sr: int, fc: float, kind: str) -> np.ndarray:
    """Zero-phase 4th-order low/high split for the crossover."""
    sos = signal.butter(4, fc, btype=kind, fs=sr, output="sos")
    return signal.sosfiltfilt(sos, y).astype(np.float32)


def multiband_denoise(y: np.ndarray, sr: int, cfg: DenoiseConfig,
                      noise_clip: np.ndarray | None = None) -> np.ndarray:
    """Clean out-of-band noise hard, in-band (snore) noise gently, then recombine.

    No gate, no DL, no time-varying gain — so the snore's amplitude envelope is left
    intact and it never "breaks". Stationary subtraction uses an auto-measured (or
    supplied) snore-free noise profile. See the `safe` preset.
    """
    import noisereduce as nr
    base = highpass(y, sr, cfg.highpass_hz)            # kill sub-snore AC rumble
    nc = noise_clip if noise_clip is not None else _auto_noise_clip(y, sr)
    nc = highpass(nc, sr, cfg.highpass_hz)
    sub = lambda pd: nr.reduce_noise(y=base, sr=sr, stationary=True,
                                     y_noise=nc, prop_decrease=pd).astype(np.float32)
    inband = sub(cfg.inband_prop)                      # gentle inside the snore band
    outband = sub(cfg.outband_prop)                    # hard outside it
    out = _split(inband, sr, cfg.xover_hz, "low") + _split(outband, sr, cfg.xover_hz, "high")
    if cfg.normalize:
        peak = np.max(np.abs(out))
        if peak > 1e-6:
            out = out / peak * 0.97
    return out.astype(np.float32)


# ── Round-2 methods (see tests/test_denoise_methods.py) ────────────────────────
#
# multi_profile_denoise — fixes the known weakness of the single global noise
#   profile: with an AC that cycles on/off, the quietest window is always an
#   AC-off moment, so the AC-on stretches are under-subtracted. Cluster the
#   quiet gaps into k noise states, denoise against each state's own profile,
#   and crossfade between the results following the detected state timeline.
#
# mmse_lsa_denoise — Ephraim-Malah MMSE log-spectral-amplitude estimator with a
#   decision-directed a-priori SNR. The classical successor to spectral
#   subtraction: its recursive SNR smoothing is what suppresses musical noise.
#
# nmf_denoise — semi-supervised NMF separation: learn a noise dictionary from
#   the quiet gaps, add free components for the snore, Wiener-mask with the
#   free components' reconstruction. Separation, not subtraction.


def _gap_frame_info(y: np.ndarray, sr: int, frame_s: float, gap_pct: float,
                    local_s: float = 20.0):
    """Frame the signal; return (frame_len, per-frame dB, gap-frame indices).

    Gap frames are the bottom `gap_pct`% WITHIN a rolling `local_s` window, not
    globally — with cycling noise the loud state's gaps are louder than the
    quiet state's snores, so a global threshold would only ever sample gaps
    from the quiet state and the loud noise state would never be profiled."""
    from scipy.ndimage import percentile_filter
    flen = max(1, int(sr * frame_s))
    n = len(y) // flen
    fr = y[: n * flen].reshape(n, flen)
    pdb = 10 * np.log10(np.mean(fr.astype(np.float64) ** 2, axis=1) + 1e-12)
    size = max(3, int(local_s / frame_s)) | 1
    local_thresh = percentile_filter(pdb, percentile=gap_pct, size=size)
    gap_idx = np.where(pdb <= local_thresh)[0]
    if len(gap_idx) == 0:
        gap_idx = np.where(pdb <= np.percentile(pdb, gap_pct))[0]
    return flen, pdb, gap_idx


def _auto_noise_frames(y: np.ndarray, sr: int, max_s: float = 6.0,
                       frame_s: float = 0.25, gap_pct: float = 20.0) -> np.ndarray:
    """Noise fingerprint built from concatenated short GAP FRAMES rather than
    one contiguous window: a contiguous window as short as a breath cycle
    inevitably swallows a snore burst, and a noise profile that contains snore
    subtracts snore (see the NMF role-flip caught in test_denoise_methods)."""
    flen, _, gap_idx = _gap_frame_info(y, sr, frame_s, gap_pct)
    n_frames = len(y) // flen
    frames = y[: n_frames * flen].reshape(n_frames, flen)
    clip = frames[gap_idx].reshape(-1)[: int(max_s * sr)]
    return clip if len(clip) >= flen else _auto_noise_clip(y, sr)


def multi_profile_denoise(y: np.ndarray, sr: int, n_profiles: int = 2,
                          prop_decrease: float = 0.9, gap_pct: float = 30.0,
                          frame_s: float = 0.5, xfade_s: float = 0.5,
                          max_clip_s: float = 10.0) -> np.ndarray:
    """Spectral subtraction with k noise profiles clustered from the quiet gaps.

    n_profiles=1 reproduces the old single-global-profile behavior (baseline)."""
    import noisereduce as nr

    flen, _, gap_idx = _gap_frame_info(y, sr, frame_s, gap_pct)
    n_frames = len(y) // flen
    frames = y[: n_frames * flen].reshape(n_frames, flen)

    if n_profiles <= 1 or len(gap_idx) < 2 * n_profiles:
        states = np.zeros(len(gap_idx), dtype=int)
        pure = np.ones(len(gap_idx), dtype=bool)
        n_profiles = 1
    else:
        # Cluster gap frames by their band-energy spectrum (log, z-scored).
        mag2 = np.abs(np.fft.rfft(frames[gap_idx] * np.hanning(flen), axis=1)) ** 2
        n_bands = 24
        bands = np.array_split(mag2, n_bands, axis=1)
        feat = np.log10(np.stack([b.mean(axis=1) for b in bands], axis=1) + 1e-12)
        feat = (feat - feat.mean(axis=0)) / (feat.std(axis=0) + 1e-9)
        from sklearn.cluster import KMeans
        km = KMeans(n_clusters=n_profiles, n_init=10, random_state=0).fit(feat)
        states = km.labels_
        # Gap frames aren't perfectly noise-only (snore tails leak in) — build
        # each profile only from the half of its cluster nearest the centroid,
        # so one mis-clustered snore-y frame can't put snore into a profile.
        dist = np.linalg.norm(feat - km.cluster_centers_[states], axis=1)
        pure = np.zeros(len(states), dtype=bool)
        for k in range(n_profiles):
            m = states == k
            pure[m] = dist[m] <= np.median(dist[m])

    # Noise state per frame: nearest-in-time gap frame's state, median-smoothed
    # (noise states are piecewise-constant over long stretches; isolated
    # mis-assigned gap frames must not flip the timeline back and forth).
    frame_state = states[np.abs(gap_idx[None, :] - np.arange(n_frames)[:, None]).argmin(axis=1)]
    if n_profiles > 1:
        from scipy.ndimage import median_filter
        frame_state = median_filter(frame_state, size=max(3, int(10.0 / frame_s)) | 1)

    max_clip = int(max_clip_s * sr)
    cleaned = []
    for k in range(n_profiles):
        sel = gap_idx[(states == k) & pure]
        if len(sel) == 0:
            sel = gap_idx[states == k]
        clip = frames[sel].reshape(-1)[:max_clip]
        cleaned.append(nr.reduce_noise(y=y, sr=sr, stationary=True, y_noise=clip,
                                       prop_decrease=prop_decrease).astype(np.float32))
    if n_profiles == 1:
        return cleaned[0][: len(y)]

    # Per-sample state weights, smoothed for a click-free crossfade at switches.
    sample_state = np.repeat(frame_state, flen)
    sample_state = np.pad(sample_state, (0, len(y) - len(sample_state)), mode="edge")
    win = max(1, int(sr * xfade_s))
    kern = np.ones(win) / win
    weights = np.stack([np.convolve((sample_state == k).astype(np.float32), kern,
                                    mode="same") for k in range(n_profiles)])
    weights /= weights.sum(axis=0, keepdims=True) + 1e-9
    out = sum(w * c[: len(y)] for w, c in zip(weights, cleaned))
    return out.astype(np.float32)


def mmse_lsa_denoise(y: np.ndarray, sr: int, noise_clip: np.ndarray | None = None,
                     n_fft: int = 1024, hop: int = 256, alpha: float = 0.98,
                     gain_floor: float = 0.05) -> np.ndarray:
    """Ephraim-Malah (1985) MMSE log-spectral-amplitude denoiser.

    `alpha` is the decision-directed smoothing of the a-priori SNR — the
    mechanism that kills musical noise relative to plain spectral subtraction."""
    from scipy.special import exp1

    nc = noise_clip if noise_clip is not None else _auto_noise_frames(y, sr)
    _, _, N = signal.stft(nc, fs=sr, nperseg=n_fft, noverlap=n_fft - hop)
    lam = np.maximum(np.mean(np.abs(N) ** 2, axis=1), 1e-12)  # noise PSD per bin

    _, _, Y = signal.stft(y, fs=sr, nperseg=n_fft, noverlap=n_fft - hop)
    mag2 = np.abs(Y) ** 2
    G = np.empty_like(mag2)
    A2_prev = mag2[:, 0]  # previous frame's cleaned amplitude²
    for i in range(mag2.shape[1]):
        gamma = np.minimum(mag2[:, i] / lam, 1000.0)          # a-posteriori SNR
        xi = alpha * A2_prev / lam + (1 - alpha) * np.maximum(gamma - 1.0, 0.0)
        xi = np.maximum(xi, 1e-4)
        v = np.maximum(xi * gamma / (1.0 + xi), 1e-8)
        g = (xi / (1.0 + xi)) * np.exp(0.5 * exp1(v))
        G[:, i] = np.clip(g, gain_floor, 1.0)
        A2_prev = (G[:, i] ** 2) * mag2[:, i]
    _, out = signal.istft(Y * G, fs=sr, nperseg=n_fft, noverlap=n_fft - hop)

    out = out[: len(y)]
    if len(out) < len(y):
        out = np.pad(out, (0, len(y) - len(out)))
    return out.astype(np.float32)


def nmf_denoise(y: np.ndarray, sr: int, noise_clip: np.ndarray | None = None,
                n_noise: int = 8, n_free: int = 8, n_iter: int = 80,
                n_fft: int = 1024, hop: int = 256) -> np.ndarray:
    """Semi-supervised NMF separation.

    A noise dictionary W_n is learned on the (auto-detected or supplied) quiet
    gaps and FROZEN; n_free extra components are free to model the snore. The
    snore estimate is a Wiener mask built from the free components only."""
    from sklearn.decomposition import NMF

    rng = np.random.default_rng(0)
    eps = 1e-9

    nc = noise_clip if noise_clip is not None else _auto_noise_frames(y, sr)
    _, _, N = signal.stft(nc, fs=sr, nperseg=n_fft, noverlap=n_fft - hop)
    Vn = np.abs(N)
    W_n = NMF(n_components=n_noise, init="nndsvda", max_iter=400,
              beta_loss="kullback-leibler", solver="mu",
              random_state=0).fit(Vn.T).components_.T          # (bins, n_noise)
    W_n /= W_n.sum(axis=0, keepdims=True) + eps

    _, _, Y = signal.stft(y, fs=sr, nperseg=n_fft, noverlap=n_fft - hop)
    V = np.abs(Y)
    n_bins, n_frames = V.shape
    W = np.hstack([W_n, rng.random((n_bins, n_free)) + eps])
    H = rng.random((n_noise + n_free, n_frames)) + eps

    # KL multiplicative updates (the standard divergence for magnitude
    # spectrograms); only the free columns of W move — the noise dict is frozen.
    ones = np.ones_like(V)
    for _ in range(n_iter):
        R = V / (W @ H + eps)
        H *= (W.T @ R) / (W.T @ ones + eps)
        R = V / (W @ H + eps)
        W[:, n_noise:] *= (R @ H[n_noise:].T) / (ones @ H[n_noise:].T + eps)
        W[:, n_noise:] /= W[:, n_noise:].sum(axis=0, keepdims=True) + eps

    # Power-domain Wiener mask from the two reconstructions.
    S2 = (W[:, n_noise:] @ H[n_noise:]) ** 2
    N2 = (W[:, :n_noise] @ H[:n_noise]) ** 2
    mask = S2 / (S2 + N2 + eps)
    _, out = signal.istft(Y * mask, fs=sr, nperseg=n_fft, noverlap=n_fft - hop)
    out = out[: len(y)]
    if len(out) < len(y):
        out = np.pad(out, (0, len(y) - len(out)))
    return out.astype(np.float32)


def denoise(y: np.ndarray, sr: int = SAMPLE_RATE, preset: str | DenoiseConfig = "gentle",
            noise_clip: np.ndarray | None = None) -> np.ndarray:
    """Run the full cleaning chain. Returns a float32 waveform at `sr`.

    Pass a measured `noise_clip` (a quiet AC-on/fan segment from the same recording)
    for best results with stationary spectral subtraction.
    """
    cfg = PRESETS[preset] if isinstance(preset, str) else preset
    if cfg.use_multiband:
        return multiband_denoise(y, sr, cfg, noise_clip)
    out = highpass(y, sr, cfg.highpass_hz)
    if cfg.notch:
        out = notch_mains(out, sr, cfg.notch_freq)
    if cfg.use_dl:
        out = dl_denoise(out, sr, dry=cfg.dl_dry)
    else:
        if noise_clip is not None:
            noise_clip = highpass(noise_clip, sr, cfg.highpass_hz)
        out = spectral_denoise(out, sr, noise_clip, cfg.stationary, cfg.prop_decrease)
    if cfg.gate:
        out = noise_gate(out, sr, cfg.gate_threshold_db)
    if cfg.normalize:
        peak = np.max(np.abs(out))
        if peak > 1e-6:
            out = out / peak * 0.97
    return out.astype(np.float32)
