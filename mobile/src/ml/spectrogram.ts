/**
 * Real-time mel-spectrogram DSP for the live Record-screen visualization.
 *
 * Turns a stream of raw PCM16 frames (from @siteed/expo-audio-studio's
 * onAudioStream callback) into normalized log-mel COLUMNS suitable for a
 * scrolling spectrogram, and — as a bonus — into the same 128-bin mel features
 * the on-device CNN wants (replacing the fake loudness-derived ones in
 * audioFeatures.ts).
 *
 * Pure + dependency-light (only fft.js) so it can be unit-tested off-device.
 * Params mirror ml-research/src/features.py: 16 kHz, n_fft 1024, hop 512,
 * fmin 50, fmax 8000.
 */
import FFT from 'fft.js';

export const SR        = 16_000;
export const N_FFT     = 1024;
export const HOP       = 512;
export const FMIN      = 50;
export const FMAX      = 8_000;
export const MEL_DISPLAY = 64;   // mel bins for the live view (cheap to render)

/**
 * Display dynamic range, in dBFS, for the live spectrogram.
 *
 * These are ABSOLUTE references, not per-column ones. An earlier version
 * normalised every column against its own peak, which meant each column's
 * loudest bin always mapped to 1.0 — so digital silence rendered as a solid
 * max-brightness block, and a whisper was pixel-identical to a shout. The
 * spectrum is scaled so a full-scale sinusoid reads ~0 dBFS (see `column`),
 * which makes these thresholds meaningful across columns.
 */
export const SPEC_DB_FLOOR = -80;   // → 0.0 (black)
export const SPEC_DB_CEIL  = 0;     // → 1.0 (full brightness)

// ── base64 → PCM ────────────────────────────────────────────────────────────────
const _B64 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
const _B64_LOOKUP = (() => {
  const t = new Int16Array(256).fill(-1);
  for (let i = 0; i < _B64.length; i++) t[_B64.charCodeAt(i)] = i;
  return t;
})();

/** Decode a base64 string to raw bytes without relying on atob/Buffer. */
export function base64ToBytes(b64: string): Uint8Array {
  let len = b64.length;
  if (b64.charCodeAt(len - 1) === 61) len--;   // strip '=' padding
  if (b64.charCodeAt(len - 1) === 61) len--;
  const out = new Uint8Array((len * 3) >> 2);
  let p = 0;
  for (let i = 0; i < len; i += 4) {
    const a = _B64_LOOKUP[b64.charCodeAt(i)];
    const b = _B64_LOOKUP[b64.charCodeAt(i + 1)];
    const c = _B64_LOOKUP[b64.charCodeAt(i + 2)];
    const d = _B64_LOOKUP[b64.charCodeAt(i + 3)];
    out[p++] = (a << 2) | (b >> 4);
    if (c !== -1) out[p++] = ((b & 15) << 4) | (c >> 2);
    if (d !== -1) out[p++] = ((c & 3) << 6) | d;
  }
  return out;
}

/** Decode raw little-endian PCM16 bytes into Float32 samples in [-1, 1]. */
export function pcm16BytesToFloat32(bytes: Uint8Array): Float32Array {
  const n = bytes.length >> 1;
  const out = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    // little-endian signed 16-bit
    let s = bytes[i * 2] | (bytes[i * 2 + 1] << 8);
    if (s >= 0x8000) s -= 0x10000;
    out[i] = s / 32768;
  }
  return out;
}

/** Decode base64-encoded little-endian PCM16 into Float32 samples in [-1, 1]. */
export function pcm16Base64ToFloat32(b64: string): Float32Array {
  return pcm16BytesToFloat32(base64ToBytes(b64));
}

// ── mel filterbank + window (precomputed once) ──────────────────────────────────
// Slaney mel scale — linear below 1 kHz, logarithmic above. This is what
// librosa uses by default (htk=False), and therefore what
// ml-research/src/features.py trains on.
//
// This module previously used the HTK formula (2595*log10(1+hz/700)). The two
// disagree substantially — for 10 bands over 50-8000 Hz the second centre lands
// at 285 Hz under HTK versus 380 Hz under Slaney — so on-device features were
// being read off a different filterbank than the CNN was trained with. The
// narrower HTK low bands were also what made bands vanish entirely at 44.1/48
// kHz, where they fall below the FFT bin spacing.
const _MEL_F_SP = 200 / 3;          // Hz per mel in the linear region
const _MEL_MIN_LOG_HZ = 1000;
const _MEL_MIN_LOG_MEL = _MEL_MIN_LOG_HZ / _MEL_F_SP;   // 15.0
const _MEL_LOGSTEP = Math.log(6.4) / 27;

const hzToMel = (hz: number): number =>
  hz >= _MEL_MIN_LOG_HZ
    ? _MEL_MIN_LOG_MEL + Math.log(hz / _MEL_MIN_LOG_HZ) / _MEL_LOGSTEP
    : hz / _MEL_F_SP;

const melToHz = (m: number): number =>
  m >= _MEL_MIN_LOG_MEL
    ? _MEL_MIN_LOG_HZ * Math.exp(_MEL_LOGSTEP * (m - _MEL_MIN_LOG_MEL))
    : m * _MEL_F_SP;

/**
 * Triangular mel filterbank, built the way librosa builds it.
 *
 * The previous version rounded each mel point down to an integer FFT bin
 * (`Math.floor((nFft+1)*hz/sr)`). At 16 kHz the bins are wide enough to absorb
 * that, but at the 44.1/48 kHz rates Android actually hands back, adjacent low
 * mel points floor onto the SAME bin. Both interior loops then have an empty
 * range, leaving an all-zero filter — that band reads 10*log10(1e-12) = -120 dB
 * for the rest of time and renders as a permanent black stripe. Measured: 1 dead
 * band at 44.1 kHz, 2 at 48 kHz, and 1 at nMels=128 even at 16 kHz.
 *
 * Keeping the mel points in Hz and evaluating the triangles against each bin's
 * true centre frequency removes the quantisation entirely, and matches
 * ml-research/src/features.py so the on-device filterbank agrees with the one
 * used for training.
 *
 * `slaney` picks the normalisation:
 *   false — unit-height triangles (librosa `norm=None`). Every band passes a
 *     tone at unity gain, which is what keeps SPEC_DB_FLOOR/CEIL meaningful as
 *     absolute dBFS. Correct for the display.
 *   true  — area-normalised (librosa's default `norm="slaney"`), where filter
 *     height falls with bandwidth. Correct for CNN features, because that is
 *     what features.py trains on — but it would break the dBFS calibration,
 *     since peak gain varies ~8x across the band.
 */
function buildMelFilterbank(nMels: number, nFft: number, sr: number,
                            fmin: number, fmax: number,
                            slaney = false): Float32Array[] {
  const nBins = (nFft >> 1) + 1;
  const melMin = hzToMel(fmin), melMax = hzToMel(fmax);

  // nMels+2 mel points, kept in Hz — no rounding to bin indices.
  const melHz = new Float64Array(nMels + 2);
  for (let i = 0; i < melHz.length; i++) {
    melHz[i] = melToHz(melMin + ((melMax - melMin) * i) / (nMels + 1));
  }
  // Centre frequency of each FFT bin.
  const binHz = new Float64Array(nBins);
  for (let k = 0; k < nBins; k++) binHz[k] = (k * sr) / nFft;

  const filters: Float32Array[] = [];
  for (let m = 0; m < nMels; m++) {
    const f = new Float32Array(nBins);
    const lo = melHz[m], mid = melHz[m + 1], hi = melHz[m + 2];
    const dLo = mid - lo, dHi = hi - mid;
    const gain = slaney ? 2 / (hi - lo) : 1;
    for (let k = 0; k < nBins; k++) {
      const hz = binHz[k];
      // Rising edge into `mid`, falling edge out of it; the min of the two
      // ramps is the triangle, clamped at zero outside [lo, hi].
      const rise = dLo > 0 ? (hz - lo) / dLo : (hz >= lo ? 1 : 0);
      const fall = dHi > 0 ? (hi - hz) / dHi : (hz <= hi ? 1 : 0);
      const w = Math.min(rise, fall);
      if (w > 0) f[k] = w * gain;
    }
    filters.push(f);
  }
  return filters;
}

function hannWindow(n: number): Float32Array {
  const w = new Float32Array(n);
  for (let i = 0; i < n; i++) w[i] = 0.5 * (1 - Math.cos((2 * Math.PI * i) / (n - 1)));
  return w;
}

// ── streamer ────────────────────────────────────────────────────────────────────

/**
 * Buffers incoming PCM and emits one normalized log-mel column per HOP.
 * Each column is Float32Array[nMels] in [0, 1] (0 = silence floor, 1 = loud),
 * ready to map through a colormap for display.
 */
export class MelSpectrogramStreamer {
  private readonly nMels: number;
  private readonly fft: FFT;
  private readonly win: Float32Array;
  private readonly filters: Float32Array[];
  private readonly fftInput: Float32Array;
  private readonly fftOutput: Float32Array;   // complex interleaved, length 2*N_FFT
  private tail = new Float32Array(0);
  /** One-sided amplitude normalisation: makes a full-scale sinusoid read ~0 dBFS. */
  private readonly ampNorm: number;
  readonly sampleRate: number;
  /** Mel bands with an all-zero filter — see the constructor. Empty is healthy. */
  readonly deadBands: number[];
  /** Reused per frame — see powerSpectrum(). */
  private readonly powerBuf: Float32Array;

  /**
   * @param nMels      mel bins per column
   * @param sampleRate rate of the incoming PCM. Android frequently ignores the
   *   requested 16 kHz and hands back 44.1/48 kHz; the filterbank must be built
   *   for the rate actually delivered or every tone lands in the wrong mel bin.
   */
  constructor(nMels: number = MEL_DISPLAY, sampleRate: number = SR) {
    this.nMels = nMels;
    this.sampleRate = sampleRate;

    const nBins = (N_FFT >> 1) + 1;
    this.powerBuf = new Float32Array(nBins);
    this.fft = new FFT(N_FFT);
    this.win = hannWindow(N_FFT);
    this.filters = buildMelFilterbank(nMels, N_FFT, sampleRate, FMIN,
                                      Math.min(FMAX, sampleRate / 2));

    // A mel band narrower than the FFT bin spacing catches no bin centre and is
    // therefore all zeros, reading -120 dB forever — a black stripe on screen, a
    // dead input to the CNN. librosa hits the same limit and warns; say so here
    // too rather than letting it pass silently. Widening N_FFT or resampling to
    // 16 kHz before this point are the two ways out.
    const deadBands: number[] = [];
    for (let m = 0; m < this.filters.length; m++) {
      let any = false;
      const f = this.filters[m];
      for (let k = 0; k < f.length; k++) if (f[k] > 0) { any = true; break; }
      if (!any) deadBands.push(m);
    }
    this.deadBands = deadBands;
    if (deadBands.length) {
      console.warn(
        `[MelSpectrogramStreamer] ${deadBands.length} mel band(s) are narrower than ` +
        `the ${(sampleRate / N_FFT).toFixed(1)} Hz FFT bin spacing at nMels=${nMels}, ` +
        `sr=${sampleRate} and will always read silent: [${deadBands.join(',')}]. ` +
        `Resample to ${SR} Hz or raise N_FFT.`);
    }
    this.fftInput = new Float32Array(N_FFT);
    this.fftOutput = this.fft.createComplexArray() as unknown as Float32Array;
    let winSum = 0;
    for (let i = 0; i < N_FFT; i++) winSum += this.win[i];
    this.ampNorm = 2 / winSum;   // coherent gain of the window, one-sided
  }

  /** Feed PCM samples; returns however many mel columns are now complete. */
  push(samples: Float32Array): Float32Array[] {
    // concat tail + new samples
    const buf = new Float32Array(this.tail.length + samples.length);
    buf.set(this.tail, 0);
    buf.set(samples, this.tail.length);

    const cols: Float32Array[] = [];
    let pos = 0;
    while (pos + N_FFT <= buf.length) {
      cols.push(this.column(buf.subarray(pos, pos + N_FFT)));
      pos += HOP;
    }
    this.tail = buf.slice(pos); // keep the unconsumed remainder
    return cols;
  }

  reset(): void { this.tail = new Float32Array(0); }

  /** Mel bins this streamer emits per column. */
  get bins(): number { return this.nMels; }

  /**
   * Windowed power spectrum of one frame, scaled so a full-scale sinusoid
   * reads ~0 dBFS. Written into `this.powerBuf`, which is reused every frame —
   * copy it if you need to keep it.
   */
  private powerSpectrum(frame: Float32Array): Float32Array {
    for (let i = 0; i < N_FFT; i++) this.fftInput[i] = frame[i] * this.win[i];
    this.fft.realTransform(this.fftOutput, this.fftInput);
    this.fft.completeSpectrum(this.fftOutput);

    const power = this.powerBuf;
    for (let k = 0; k < power.length; k++) {
      const re = this.fftOutput[2 * k], im = this.fftOutput[2 * k + 1];
      // Scale to signal amplitude so the dB values below are true dBFS.
      const mag = Math.sqrt(re * re + im * im) * this.ampNorm;
      power[k] = mag * mag;
    }
    return power;
  }

  /** Project a power spectrum through the mel filterbank to a display column. */
  private melColumn(power: Float32Array): Float32Array {
    // Map each bin against the ABSOLUTE [SPEC_DB_FLOOR, SPEC_DB_CEIL] window.
    // Deliberately not relative to this column's own peak: that would make
    // silence as bright as a snore (see the constants' doc comment).
    const span = SPEC_DB_CEIL - SPEC_DB_FLOOR;
    const nBins = power.length;
    const out = new Float32Array(this.nMels);
    for (let m = 0; m < this.nMels; m++) {
      const f = this.filters[m];
      let e = 0;
      for (let k = 0; k < nBins; k++) e += f[k] * power[k];
      const db = 10 * Math.log10(e + 1e-12);
      out[m] = Math.max(0, Math.min(1, (db - SPEC_DB_FLOOR) / span));
    }
    return out;
  }

  private column(frame: Float32Array): Float32Array {
    return this.melColumn(this.powerSpectrum(frame));
  }

}

// ── colormap + RGBA packing (pure; used by LiveSpectrogram with Skia) ───────────

// magma control points (perceptually-uniform, dark→bright) for value 0→1.
const _MAGMA: [number, number, number][] = [
  [0, 0, 4], [81, 18, 124], [183, 55, 121], [252, 137, 97], [252, 253, 191],
];

/** Map a normalized magnitude [0,1] to an [r,g,b] magma colour (0-255). */
export function magma(v: number): [number, number, number] {
  v = v <= 0 ? 0 : v >= 1 ? 1 : v;
  const seg = (_MAGMA.length - 1) * v;
  const i = Math.floor(seg);
  const f = seg - i;
  const a = _MAGMA[i];
  const b = _MAGMA[Math.min(i + 1, _MAGMA.length - 1)];
  return [
    Math.round(a[0] + (b[0] - a[0]) * f),
    Math.round(a[1] + (b[1] - a[1]) * f),
    Math.round(a[2] + (b[2] - a[2]) * f),
  ];
}

/**
 * Pack a list of mel columns into a row-major RGBA8888 byte buffer for a
 * width=columns.length, height=nMels image. Low frequencies are placed at the
 * BOTTOM (y flipped), the conventional spectrogram orientation.
 */
export function packColumnsToRGBA(columns: Float32Array[], nMels: number): {
  bytes: Uint8Array; width: number; height: number;
} {
  const width = Math.max(1, columns.length);
  const height = nMels;
  const bytes = new Uint8Array(width * height * 4);
  for (let x = 0; x < columns.length; x++) {
    const col = columns[x];
    for (let m = 0; m < nMels; m++) {
      const [r, g, b] = magma(col[m]);
      const y = nMels - 1 - m;            // flip: low freq at bottom
      const idx = (y * width + x) * 4;
      bytes[idx] = r; bytes[idx + 1] = g; bytes[idx + 2] = b; bytes[idx + 3] = 255;
    }
  }
  return { bytes, width, height };
}
