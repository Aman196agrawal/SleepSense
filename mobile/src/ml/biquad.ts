/**
 * Streaming IIR filters for the live "cleaned audio" waveform.
 *
 * The spectral subtraction in denoise.ts cleans a SPECTRUM, which is all the
 * spectrogram view needs. A waveform plot needs cleaned audio in the time
 * domain, and recovering that from a modified spectrum means an inverse STFT
 * with overlap-add — more machinery, and it adds a frame of latency to a view
 * whose whole point is being live.
 *
 * Time-domain filtering gives genuinely cleaned samples for a fraction of the
 * cost and no latency, and it is what the offline `safe` preset does first
 * anyway (scipy `butter(4, 70, 'highpass')` before anything else).
 *
 * Transposed direct form II: fewer state variables than DF1 and better
 * numerical behaviour in float32 than direct form I, which matters because
 * this runs continuously for hours.
 *
 * Pure and dependency-free so it can be unit-tested off-device.
 */

/** One second-order section. Coefficients are normalised so a0 == 1. */
export class Biquad {
  private z1 = 0;
  private z2 = 0;

  constructor(
    private readonly b0: number, private readonly b1: number,
    private readonly b2: number, private readonly a1: number,
    private readonly a2: number,
  ) {}

  /** Filter one sample, advancing the internal state. */
  process(x: number): number {
    const y = this.b0 * x + this.z1;
    this.z1 = this.b1 * x - this.a1 * y + this.z2;
    this.z2 = this.b2 * x - this.a2 * y;
    return y;
  }

  reset(): void { this.z1 = 0; this.z2 = 0; }
}

/** RBJ cookbook high-pass. */
export function highpassBiquad(fc: number, sr: number, q: number): Biquad {
  const w0 = (2 * Math.PI * fc) / sr;
  const cos = Math.cos(w0), sin = Math.sin(w0);
  const alpha = sin / (2 * q);
  const a0 = 1 + alpha;
  return new Biquad(
    ((1 + cos) / 2) / a0,
    (-(1 + cos)) / a0,
    ((1 + cos) / 2) / a0,
    (-2 * cos) / a0,
    (1 - alpha) / a0,
  );
}

/** RBJ cookbook low-pass. */
export function lowpassBiquad(fc: number, sr: number, q: number): Biquad {
  const w0 = (2 * Math.PI * fc) / sr;
  const cos = Math.cos(w0), sin = Math.sin(w0);
  const alpha = sin / (2 * q);
  const a0 = 1 + alpha;
  return new Biquad(
    ((1 - cos) / 2) / a0,
    (1 - cos) / a0,
    ((1 - cos) / 2) / a0,
    (-2 * cos) / a0,
    (1 - alpha) / a0,
  );
}

/**
 * Q values for the two sections of a 4th-order Butterworth, matching what
 * scipy's `butter(4, ...)` produces. Cascading two biquads at these Qs gives a
 * maximally flat passband and a 24 dB/octave rolloff.
 */
const BUTTERWORTH_4_Q = [0.54119610, 1.30656296];

/**
 * Band-pass isolating the snore band, mirroring the `safe` preset's intent:
 * strip the AC rumble below the snore fundamental and the fan hiss above the
 * harmonics, leave everything between untouched.
 *
 * The low edge does most of the visible work on a waveform — mains hum at
 * 50/100 Hz is a large, slow component, so removing it changes the shape of the
 * trace rather than just its texture.
 */
export class SnoreBandFilter {
  private readonly sections: Biquad[];

  constructor(
    sampleRate: number,
    readonly lowHz = 70,      // safe preset: highpass_hz = 70
    readonly highHz = 1400,   // safe preset: xover_hz = 1400
  ) {
    const nyq = sampleRate / 2;
    const hp = Math.min(lowHz, nyq * 0.95);
    const lp = Math.min(highHz, nyq * 0.95);
    this.sections = [
      ...BUTTERWORTH_4_Q.map(q => highpassBiquad(hp, sampleRate, q)),
      ...BUTTERWORTH_4_Q.map(q => lowpassBiquad(lp, sampleRate, q)),
    ];
  }

  /**
   * Filter a block. Returns a new array; state carries across calls so
   * consecutive blocks join without a seam or click.
   */
  process(input: Float32Array): Float32Array {
    const out = new Float32Array(input.length);
    const s = this.sections;
    for (let i = 0; i < input.length; i++) {
      let v = input[i];
      for (let j = 0; j < s.length; j++) v = s[j].process(v);
      out[i] = v;
    }
    return out;
  }

  reset(): void { for (const s of this.sections) s.reset(); }
}
