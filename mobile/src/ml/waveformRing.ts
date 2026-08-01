/**
 * Ring buffer + pixel reduction behind the live waveform.
 *
 * Split out of LiveWaveform.tsx so it can be tested off-device: the wrap-around
 * arithmetic and the samples-to-columns reduction are the parts most likely to
 * be subtly wrong, and neither needs React or Skia to exercise.
 */

/** Interleaved x,y screen coordinates: [x0, y0, x1, y1, ...]. */
export type PointBuffer = { xy: Float32Array; count: number };

export class WaveformRing {
  private ring: Float32Array;
  private write = 0;
  private filled = 0;

  constructor(capacity: number) {
    this.ring = new Float32Array(Math.max(2, capacity));
  }

  get capacity(): number { return this.ring.length; }
  get length(): number { return this.filled; }

  /** Resize, discarding history — the visible time span changed. */
  resize(capacity: number): void {
    this.ring = new Float32Array(Math.max(2, capacity));
    this.write = 0;
    this.filled = 0;
  }

  clear(): void {
    this.ring.fill(0);
    this.write = 0;
    this.filled = 0;
  }

  push(samples: Float32Array): void {
    if (!samples.length) return;
    const cap = this.ring.length;
    // A block larger than the whole window would overwrite itself; only its
    // tail can still be visible, so skip straight to that.
    const start = samples.length > cap ? samples.length - cap : 0;
    let w = this.write;
    for (let i = start; i < samples.length; i++) {
      this.ring[w] = samples[i];
      w = w + 1 === cap ? 0 : w + 1;
    }
    this.write = w;
    this.filled = Math.min(cap, this.filled + (samples.length - start));
  }

  /** Oldest-to-newest copy of the live samples. For tests and debugging. */
  toArray(): Float32Array {
    const out = new Float32Array(this.filled);
    const cap = this.ring.length;
    const oldest = (this.write - this.filled + cap) % cap;
    for (let i = 0; i < this.filled; i++) out[i] = this.ring[(oldest + i) % cap];
    return out;
  }

  /**
   * Reduce to one point per pixel column.
   *
   * There are far more samples than columns — 80 ms at 16 kHz is 1280 samples
   * across ~350 px — so each column takes the sample with the largest absolute
   * value in its span. Averaging would flatten the peaks and make a loud trace
   * look quiet; taking the extreme preserves the true height of the waveform.
   *
   * `out` is reused across frames when supplied, since this runs every frame.
   */
  toPoints(width: number, height: number, yRange: number,
           out?: Float32Array): PointBuffer {
    const cols = Math.max(2, Math.min(Math.floor(width), this.filled));
    const xy = out && out.length >= cols * 2 ? out : new Float32Array(cols * 2);
    if (this.filled < 2) return { xy, count: 0 };

    const cap = this.ring.length;
    const oldest = (this.write - this.filled + cap) % cap;
    const mid = height / 2;
    const scale = yRange > 0 ? mid / yRange : 0;
    const per = this.filled / cols;

    for (let c = 0; c < cols; c++) {
      const from = Math.floor(c * per);
      const to = Math.max(from + 1, Math.min(this.filled, Math.floor((c + 1) * per)));
      let extreme = 0;
      for (let i = from; i < to; i++) {
        const v = this.ring[(oldest + i) % cap];
        if (Math.abs(v) >= Math.abs(extreme)) extreme = v;
      }
      let y = mid - extreme * scale;
      if (y < 0) y = 0; else if (y > height) y = height;
      xy[c * 2] = (c / (cols - 1)) * width;
      xy[c * 2 + 1] = y;
    }
    return { xy, count: cols };
  }
}
