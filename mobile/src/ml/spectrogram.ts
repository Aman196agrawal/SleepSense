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

/** Decode base64-encoded little-endian PCM16 into Float32 samples in [-1, 1]. */
export function pcm16Base64ToFloat32(b64: string): Float32Array {
  const bytes = base64ToBytes(b64);
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

// ── mel filterbank + window (precomputed once) ──────────────────────────────────
const hzToMel = (hz: number) => 2595 * Math.log10(1 + hz / 700);
const melToHz = (m: number) => 700 * (10 ** (m / 2595) - 1);

function buildMelFilterbank(nMels: number, nFft: number, sr: number,
                            fmin: number, fmax: number): Float32Array[] {
  const nBins = (nFft >> 1) + 1;
  const melMin = hzToMel(fmin), melMax = hzToMel(fmax);
  // nMels+2 mel points → triangular filters
  const points = new Float32Array(nMels + 2);
  for (let i = 0; i < points.length; i++) {
    const hz = melToHz(melMin + ((melMax - melMin) * i) / (nMels + 1));
    points[i] = Math.floor(((nFft + 1) * hz) / sr); // → fft bin index
  }
  const filters: Float32Array[] = [];
  for (let m = 1; m <= nMels; m++) {
    const f = new Float32Array(nBins);
    const left = points[m - 1], center = points[m], right = points[m + 1];
    for (let k = left; k < center; k++) if (center > left) f[k] = (k - left) / (center - left);
    for (let k = center; k < right; k++) if (right > center) f[k] = (right - k) / (right - center);
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
  private readonly topDb = 80;

  constructor(nMels: number = MEL_DISPLAY) {
    this.nMels = nMels;
    this.fft = new FFT(N_FFT);
    this.win = hannWindow(N_FFT);
    this.filters = buildMelFilterbank(nMels, N_FFT, SR, FMIN, FMAX);
    this.fftInput = new Float32Array(N_FFT);
    this.fftOutput = this.fft.createComplexArray() as unknown as Float32Array;
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

  private column(frame: Float32Array): Float32Array {
    // window
    for (let i = 0; i < N_FFT; i++) this.fftInput[i] = frame[i] * this.win[i];
    this.fft.realTransform(this.fftOutput, this.fftInput);
    this.fft.completeSpectrum(this.fftOutput);

    const nBins = (N_FFT >> 1) + 1;
    const power = new Float32Array(nBins);
    for (let k = 0; k < nBins; k++) {
      const re = this.fftOutput[2 * k], im = this.fftOutput[2 * k + 1];
      power[k] = re * re + im * im;
    }

    const out = new Float32Array(this.nMels);
    let maxDb = -Infinity;
    for (let m = 0; m < this.nMels; m++) {
      const f = this.filters[m];
      let e = 0;
      for (let k = 0; k < nBins; k++) e += f[k] * power[k];
      const db = 10 * Math.log10(e + 1e-10);
      out[m] = db;
      if (db > maxDb) maxDb = db;
    }
    // normalize to [0,1] over a fixed topDb range below the per-column max
    for (let m = 0; m < this.nMels; m++) {
      out[m] = Math.max(0, Math.min(1, (out[m] - (maxDb - this.topDb)) / this.topDb));
    }
    return out;
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
