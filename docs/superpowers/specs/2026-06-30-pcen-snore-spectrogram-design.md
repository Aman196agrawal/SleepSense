# PCEN Snore Spectrogram — Design

**Date:** 2026-06-30
**Status:** Approved (design); pending spec review
**Scope:** Visualization + reusable transform only. ML front-end integration is a
separate, later spec.

## Background

SleepSense cleans multi-hour night recordings of a sleeper whose AC cycles on/off
and fan runs continuously. The AC/fan noise **overlaps the snore in frequency**
(80–1400 Hz), so amplitude/spectral denoisers cannot remove the in-band noise
without breaking the snore (proven this cycle: a ~3 dB non-breaking ceiling, and
speech-trained DL denoisers re-modulate the snore envelope). The shipped `safe`
preset cleans the out-of-band rumble/hiss but leaves the in-band hum.

For **visualization** (report / mentor) and as a future **ML feature front-end**,
we don't need an invertible, listenable signal — we need a representation where the
snore stands out from the noise floor. **PCEN (Per-Channel Energy Normalization)**
is built for exactly this: a per-frequency automatic gain control (AGC) that
suppresses a slowly-varying background and boosts transients, followed by dynamic
range compression. It is cheap, well-established in noisy sound-event detection,
and `librosa.pcen()` implements it.

## Goal

Deliver a **snore-tuned PCEN transform** plus a **log-mel vs PCEN comparison
figure** on the real recordings, demonstrating that PCEN flattens the stationary
AC/fan floor and makes the snore pop. The transform is written as a pure
`waveform -> matrix` function so the same code can later feed the classifier.

Non-goals (YAGNI): ML/classifier wiring, audio reconstruction (PCEN is not
invertible), parameter UIs, batch processing of full files.

## Architecture

Three units with clean boundaries:

### 1. `ml-research/src/pcen.py` — the transform (no matplotlib)

```python
def pcen_spectrogram(
    y: np.ndarray, sr: int = 16_000, *,
    fmax: float = 2000.0,
    n_fft: int = 1024, hop_length: int = 512, n_mels: int = 128, fmin: float = 50.0,
    time_constant: float = 0.4, gain: float = 0.98, bias: float = 2.0,
    power: float = 0.5, eps: float = 1e-6,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (pcen_matrix [n_mels x n_frames], times_s, mel_freqs_hz)."""
```

- Computes a **mel power spectrogram** (reuse the `features.py` STFT params:
  `N_FFT`, `HOP_LENGTH`, `N_MELS`, `F_MIN`; `fmax` defaults to 2000 Hz to focus on
  the snore band rather than features.py's 8000).
- Applies `librosa.pcen(S, sr=sr, hop_length=hop_length, time_constant=...,
  gain=gain, bias=bias, power=power, eps=eps)`.
- Returns the PCEN matrix plus time (seconds) and mel-center-frequency (Hz) axes.
- Pure function: deterministic, no I/O, no plotting. This is the reuse seam for the
  future ML front-end.

A companion helper for the comparison metric:

```python
def active_gap_contrast(M: np.ndarray, sr: int, hop_length: int) -> float:
    """Mean PCEN value in snore-active frames minus that in gap frames.
    Active/gap frames chosen by per-frame energy percentile (same framing idea as
    metrics.py). Higher = snore stands out more from the background."""
```

### 2. `src/visualize.py` — drawing (additions)

- `draw_pcen(ax, M, times, freqs, title="")` — render a PCEN matrix on an axis,
  parallel to the existing `draw_spectrogram` / `draw_mel_spectrogram`.
- `logmel_vs_pcen(y, sr, fmax=2000, title="")` — stacked figure: log-mel on top,
  PCEN below (parallel to the existing `raw_vs_clean`). Returns a Figure.

### 3. Driver — render on a real recording

A small script (`ml-research/render_pcen.py`) or notebook cell that:
- Decodes the raw source the **same way** the cleaned files were made (full
  contiguous decode via `batch_denoise.decode_to_wav`, then read the window) — NOT
  `load_slice`/`-ss`, to avoid the 100–200 ms decode-drift gotcha.
- Renders `logmel_vs_pcen` at 2–3 offsets across the night.
- Saves PNGs under `ml-research/output/` (gitignored).

## Data flow

```
waveform (same-decode-path slice)
  -> mel power spectrogram (features.py STFT params, fmax=2000)
  -> librosa.pcen (per-channel AGC + range compression)
  -> PCEN matrix  --> draw_pcen / logmel_vs_pcen --> PNG
                  \-> active_gap_contrast --> validation number
```

No audio output (PCEN is non-invertible — acceptable for visualization).

## Parameter tuning (the real work)

PCEN's per-channel floor estimate `M` is a first-order IIR smoother of the energy;
`time_constant` sets how fast it adapts. It must be:
- **slow enough** that the AGC tracks only the *background* (AC floor cycles over
  minutes) and lets snore bursts (~0.5–2 s) pop above it;
- not so slow it fails to adapt to AC on/off.

Plan:
1. Start at librosa defaults (`time_constant=0.4`, `gain=0.98`, `bias=2`,
   `power=0.5`).
2. **Sweep `time_constant`** (e.g. 0.2, 0.4, 0.8, 1.5, 3.0 s) on a real snore slice;
   score each with `active_gap_contrast`.
3. Pick the value maximizing contrast while keeping the snore visually continuous;
   adjust `gain`/`bias`/`power` only if needed. Record chosen defaults in `pcen.py`.

## Success criteria

- **Visual:** in the PCEN panel the snore is clearly above a near-uniform
  background, vs the noisy wash in the log-mel panel — at 2–3 offsets across the
  night (so AC-on and AC-off regions are both covered).
- **Quantitative:** `active_gap_contrast(PCEN) > active_gap_contrast(log-mel)` on
  the same real slices.

## Testing

A single standalone script `ml-research/test_pcen.py` (matching the repo's flat
script style — `train.py`, `batch_denoise.py`), runnable directly:
- **Unit (`pcen.py`):** output shape `(n_mels, n_frames)`, all finite, deterministic
  across runs; handles silent input and very short (< one frame) input without error.
- **Validation:** contrast metric beats log-mel on a real slice; comparison figures
  rendered at multiple offsets.

## Files

| File | Change |
|------|--------|
| `ml-research/src/pcen.py` | NEW — `pcen_spectrogram`, `active_gap_contrast` |
| `ml-research/src/visualize.py` | ADD — `draw_pcen`, `logmel_vs_pcen` |
| `ml-research/render_pcen.py` | NEW — driver rendering the comparison on a real file |
| `ml-research/test_pcen.py` | NEW — standalone unit + validation checks |

## Open questions

None blocking. Parameter defaults are finalized during the tuning step and baked
into `pcen.py`.
