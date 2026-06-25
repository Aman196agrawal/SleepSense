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
  gentle     — light touch; safest for ML training audio (least artifacts)
  medium     — balanced; good default for visualization
  aggressive — maximum noise removal + gate; best for human listening
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


PRESETS = {
    "gentle":     DenoiseConfig(highpass_hz=60, prop_decrease=0.6, stationary=True,  gate=False),
    "medium":     DenoiseConfig(highpass_hz=65, prop_decrease=0.85, stationary=False, gate=False),
    "aggressive": DenoiseConfig(highpass_hz=70, prop_decrease=0.95, stationary=False, gate=True,
                                gate_threshold_db=-42.0),
}


def denoise(y: np.ndarray, sr: int = SAMPLE_RATE, preset: str | DenoiseConfig = "medium",
            noise_clip: np.ndarray | None = None) -> np.ndarray:
    """Run the full cleaning chain. Returns a float32 waveform at `sr`.

    Pass a measured `noise_clip` (a quiet AC-on/fan segment from the same recording)
    for best results with stationary spectral subtraction.
    """
    cfg = PRESETS[preset] if isinstance(preset, str) else preset
    out = highpass(y, sr, cfg.highpass_hz)
    if cfg.notch:
        out = notch_mains(out, sr, cfg.notch_freq)
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
