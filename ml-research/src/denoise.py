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
