/**
 * Streaming spectral subtraction for the live "cleaned" spectrogram.
 *
 * The offline cleaner (ml-research/src/denoise.py, `safe` preset) runs
 * noisereduce + scipy over a whole file. None of that can run on the phone, and
 * it needs the entire recording up front anyway.
 *
 * The key simplification is that the live view only needs a cleaned PICTURE,
 * not cleaned AUDIO. Nothing is ever played back or resynthesised, so there is
 * no inverse STFT and no phase to preserve — the work happens entirely on the
 * power spectrum that MelSpectrogramStreamer already computes for every frame,
 * which makes it cheap enough for the audio callback.
 *
 * The approach mirrors the `safe` preset rather than inventing something new:
 *   - a stationary noise floor estimated per frequency bin
 *   - subtracted GENTLY inside the snore band (80-1400 Hz) so a snore's
 *     envelope is never chewed into, and HARD outside it, where there is no
 *     snore to damage and the AC/fan hiss lives
 *   - a spectral floor, so bins never go to true zero (that is what produces
 *     "musical noise" — isolated shimmering artefacts)
 *
 * Pure and dependency-free so it can be unit-tested off-device.
 */

/** Defaults mirror the `safe` preset in ml-research/src/denoise.py. */
export const DENOISE_DEFAULTS = {
  /** Snore band upper edge. Below this, tread carefully. */
  crossoverHz: 1400,
  /** Everything under here is AC rumble below the snore fundamental. */
  highpassHz: 70,
  /**
   * Over-subtraction factors: how many times the estimated noise power to
   * remove. Above 1 because the floor estimate tracks the noise MINIMUM, while
   * the noise actually present in any frame fluctuates above that — subtracting
   * exactly 1x the minimum barely dents the average.
   *
   * These are NOT the `inband_prop` / `outband_prop` numbers from the `safe`
   * preset. Those are noisereduce's `prop_decrease`, which blends a computed
   * gain mask and is a different quantity; reusing 0.65/0.97 here removed only
   * ~1 dB. What carries over from `safe` is the shape of the idea — tread
   * gently where the snore lives, cut hard where only hiss does.
   */
  inBandAlpha: 1.5,
  outBandAlpha: 3.0,
  /**
   * Residual kept as a fraction of the original bin, in power terms (-20 dB).
   * Without a floor, subtracted bins collapse to the epsilon and the display
   * fills with speckle.
   */
  spectralFloor: 0.01,
} as const;

export type DenoiseConfig = typeof DENOISE_DEFAULTS;

/**
 * Per-bin noise floor, tracked continuously.
 *
 * Snores are loud and brief; the AC/fan floor is quiet and persistent. The
 * estimate therefore settles on the level of the quiet stretches, and is
 * strictly rate-limited on the way up so a snore is never learned as "noise" —
 * that would subtract the snore from itself.
 *
 * This is the streaming counterpart of `_auto_noise_clip`, which picks the
 * quietest 2 s window of a finished recording.
 */
export class NoiseFloorTracker {
  private floor: Float32Array | null = null;
  private frames = 0;

  /**
   * Downward smoothing when the frame is quieter than the estimate.
   *
   * Deliberately slow (~200 frames, about 6 s at a 32 ms hop) so the estimate
   * settles on the MEAN level of the quiet stretches. A fast decay chases every
   * downward fluctuation and converges near the noise MINIMUM instead — and
   * broadband hiss fluctuates enough that its minimum sits roughly 10x under
   * its mean, so subtracting that removed only ~2 dB.
   */
  private readonly decay: number;
  /**
   * Upward growth cap, as a multiplier per frame.
   *
   * The floor may only creep up by this factor regardless of how loud the frame
   * is. An exponential average in this direction does not work: even a 0.0005
   * leak per frame compounds to 21x over the 40 frames a 1.3 s snore occupies,
   * and an inflated floor gets subtracted straight back out of the snore.
   * 1.002/frame is ~13% over that same burst, and still lets a genuinely
   * louder room settle in over a few seconds.
   */
  private readonly riseRate: number;
  /** Frames before the estimate is trustworthy (~2 s at a 32 ms hop). */
  private readonly warmup: number;

  constructor(decay = 0.995, riseRate = 1.002, warmup = 60) {
    this.decay = decay;
    this.riseRate = riseRate;
    this.warmup = warmup;
  }

  /** True once enough frames have been seen for the estimate to mean anything. */
  get ready(): boolean { return this.frames >= this.warmup; }

  /** Current estimate, or null before the first frame. Not a copy — do not mutate. */
  get estimate(): Float32Array | null { return this.floor; }

  /** Feed one frame's power spectrum. */
  update(power: Float32Array): void {
    if (!this.floor || this.floor.length !== power.length) {
      // Seed from the first frame rather than zeros, so the tracker does not
      // spend its warm-up climbing from silence and over-subtracting.
      this.floor = Float32Array.from(power);
      this.frames = 1;
      return;
    }
    const f = this.floor;
    for (let k = 0; k < f.length; k++) {
      const p = power[k];
      if (p < f[k]) {
        // Quieter than the estimate: this is the floor showing itself. Follow it.
        f[k] = this.decay * f[k] + (1 - this.decay) * p;
      } else {
        // Louder: could be a snore. Creep up by a bounded factor at most, and
        // never past the observation itself.
        const capped = f[k] * this.riseRate;
        f[k] = capped < p ? capped : p;
      }
    }
    this.frames++;
  }

  reset(): void { this.floor = null; this.frames = 0; }
}

/**
 * Subtract the tracked noise floor from one power spectrum.
 *
 * Writes into `out` (allocated by the caller and reused across frames — this
 * runs on every audio frame, so per-frame allocation is worth avoiding).
 * Returns `out`.
 *
 * Before the tracker has warmed up the input is copied through unchanged: a
 * half-formed floor estimate produces worse output than no subtraction, and a
 * viewer comparing two panels would read the difference as a real effect.
 */
export function spectralSubtract(
  power: Float32Array,
  tracker: NoiseFloorTracker,
  binHz: Float64Array | Float32Array,
  cfg: DenoiseConfig,
  out: Float32Array,
): Float32Array {
  const floor = tracker.estimate;
  if (!floor || !tracker.ready) {
    out.set(power);
    return out;
  }
  for (let k = 0; k < power.length; k++) {
    const hz = binHz[k];
    if (hz < cfg.highpassHz) {
      // Below the snore fundamental this is AC rumble; the offline chain
      // high-passes it away, so mirror that instead of subtracting.
      out[k] = power[k] * cfg.spectralFloor;
      continue;
    }
    const alpha = hz <= cfg.crossoverHz ? cfg.inBandAlpha : cfg.outBandAlpha;
    const subtracted = power[k] - alpha * floor[k];
    const minimum = cfg.spectralFloor * power[k];
    out[k] = subtracted > minimum ? subtracted : minimum;
  }
  return out;
}
