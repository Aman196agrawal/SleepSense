/**
 * Off-device verification harness for src/ml/spectrogram.ts.
 *
 * Transpiles the TS module in-memory (no type-check) and exercises the pure DSP:
 *   - PCM16 base64 decode round-trips a known sample
 *   - a pure sine tone deposits its energy in the mel bin that matches its pitch,
 *     and that bin moves UP as the tone frequency rises
 *   - colormap endpoints + RGBA packing dims / low-freq-at-bottom orientation
 *
 * Run from mobile/:  node scripts/verify_spectrogram.cjs
 */
const fs = require('fs');
const path = require('path');
const Module = require('module');
const ts = require('typescript');

const TS_OPTS = {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2019, esModuleInterop: true,
  },
};

// Register a .ts handler so modules can import each other (spectrogram.ts pulls
// in ./denoise). Node probes the keys of require.extensions when resolving an
// extensionless path, so this also makes `require('./denoise')` find denoise.ts.
require.extensions['.ts'] = (m, filename) => {
  m._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), TS_OPTS).outputText, filename);
};

// transpile a TS module in-memory (no type-check) and load it as CommonJS
function loadTs(srcPath) {
  const js = ts.transpileModule(fs.readFileSync(srcPath, 'utf8'), TS_OPTS).outputText;
  const m = new Module(srcPath);
  m.filename = srcPath;
  m.paths = Module._nodeModulePaths(path.dirname(srcPath));
  m._compile(js, srcPath);
  return m.exports;
}

const ML = path.join(__dirname, '..', 'src', 'ml');
const spec = loadTs(path.join(ML, 'spectrogram.ts'));
const wav = loadTs(path.join(ML, 'wav.ts'));

let failures = 0;
const ok = (cond, msg) => { console.log(`${cond ? '  ok  ' : ' FAIL '} ${msg}`); if (!cond) failures++; };

// ── 1. PCM16 base64 decode ──────────────────────────────────────────────
(() => {
  const samples = Int16Array.from([0, 32767, -32768, 1000, -1000]);
  const buf = Buffer.from(samples.buffer, samples.byteOffset, samples.byteLength);
  const b64 = buf.toString('base64');
  const f = spec.pcm16Base64ToFloat32(b64);
  ok(f.length === samples.length, `decoded ${f.length} samples (expected ${samples.length})`);
  ok(f[0] === 0, 'sample 0 -> 0.0');
  ok(Math.abs(f[1] - 32767 / 32768) < 1e-4, 'sample 32767 -> ~+1.0');
  ok(f[2] === -1, 'sample -32768 -> -1.0');
})();

// ── 2. sine tone lands in the right mel bin, and moves up with pitch ─────
const SR = spec.SR;
function sine(freq, secs) {
  const n = Math.round(SR * secs);
  const out = new Float32Array(n);
  for (let i = 0; i < n; i++) out[i] = 0.8 * Math.sin((2 * Math.PI * freq * i) / SR);
  return out;
}
function peakMelBin(freq) {
  const s = new spec.MelSpectrogramStreamer(spec.MEL_DISPLAY);
  const cols = s.push(sine(freq, 0.5));            // ~15 columns of steady tone
  const mid = cols[Math.floor(cols.length / 2)];   // a settled column
  let peak = 0;
  for (let i = 1; i < mid.length; i++) if (mid[i] > mid[peak]) peak = i;
  return { peak, bins: s.bins, cols: cols.length };
}

const low = peakMelBin(200);
const mid = peakMelBin(1000);
const high = peakMelBin(4000);
console.log(`    peak mel bin: 200Hz=${low.peak}  1000Hz=${mid.peak}  4000Hz=${high.peak}  (of ${low.bins})`);
ok(low.cols > 5, `streamer emitted ${low.cols} columns for a 0.5s tone`);
ok(low.peak < mid.peak && mid.peak < high.peak, 'peak mel bin rises monotonically with tone frequency');
ok(low.peak < high.bins * 0.4, '200 Hz peak sits in the lower mel bands');
ok(high.peak > high.bins * 0.5, '4000 Hz peak sits in the upper mel bands');

// ── 3. colormap + RGBA packing ──────────────────────────────────────────
(() => {
  const dark = spec.magma(0), bright = spec.magma(1);
  ok(dark[0] + dark[1] + dark[2] < 30, `magma(0) is near-black [${dark}]`);
  ok(bright[0] > 200 && bright[1] > 200, `magma(1) is bright [${bright}]`);

  const nMels = 4;
  // two columns; column-1 has all energy in the LOWEST mel bin (index 0)
  const c0 = new Float32Array(nMels);
  const c1 = new Float32Array(nMels); c1[0] = 1; // low freq = bright
  const { bytes, width, height } = spec.packColumnsToRGBA([c0, c1], nMels);
  ok(width === 2 && height === nMels, `packed image ${width}x${height}`);
  // low freq (mel 0) must render at the BOTTOM row (y = height-1), column x=1
  const idx = ((height - 1) * width + 1) * 4;
  ok(bytes[idx] > 200, 'low-freq energy renders at the BOTTOM row (bright)');
  const topIdx = (0 * width + 1) * 4;
  ok(bytes[topIdx] + bytes[topIdx + 1] + bytes[topIdx + 2] < 30, 'top row stays dark for a low-freq-only column');
})();

// ── 4. WAV encode (wav.ts) ──────────────────────────────────────────────
(() => {
  // base64 encoder matches Node's Buffer for assorted lengths
  for (const len of [0, 1, 2, 3, 4, 5, 100, 257]) {
    const b = new Uint8Array(len);
    for (let i = 0; i < len; i++) b[i] = (i * 37 + 11) & 0xff;
    const mine = wav.bytesToBase64(b);
    const ref = Buffer.from(b).toString('base64');
    ok(mine === ref, `bytesToBase64 matches Buffer for len=${len}`);
  }

  // a 1-second mono 16k PCM16 chunk -> WAV with correct header
  const sr = 16000, n = sr; // 1s
  const pcm = new Uint8Array(n * 2); // zeros are fine for header checks
  const b64 = wav.encodeWavBase64([pcm], sr, 1, 16);
  const buf = Buffer.from(b64, 'base64');
  ok(buf.length === 44 + n * 2, `WAV size = 44 + data (${buf.length})`);
  ok(buf.toString('ascii', 0, 4) === 'RIFF', 'WAV starts with RIFF');
  ok(buf.toString('ascii', 8, 12) === 'WAVE', 'WAVE tag present');
  ok(buf.toString('ascii', 12, 16) === 'fmt ', 'fmt chunk present');
  ok(buf.toString('ascii', 36, 40) === 'data', 'data chunk present');
  ok(buf.readUInt32LE(4) === 36 + n * 2, 'RIFF chunk size correct');
  ok(buf.readUInt16LE(20) === 1, 'audioFormat = PCM (1)');
  ok(buf.readUInt16LE(22) === 1, 'channels = 1');
  ok(buf.readUInt32LE(24) === sr, `sampleRate = ${sr}`);
  ok(buf.readUInt32LE(28) === sr * 2, 'byteRate = sr*2');
  ok(buf.readUInt16LE(32) === 2, 'blockAlign = 2');
  ok(buf.readUInt16LE(34) === 16, 'bitsPerSample = 16');
  ok(buf.readUInt32LE(40) === n * 2, 'data chunk size correct');

  // multiple PCM parts concatenate in order
  const a = Uint8Array.from([1, 2]), c = Uint8Array.from([3, 4]);
  const multi = Buffer.from(wav.encodeWavBase64([a, c], sr, 1, 16), 'base64');
  ok(multi[44] === 1 && multi[45] === 2 && multi[46] === 3 && multi[47] === 4, 'PCM parts concatenated in order');
})();

// ── mel filterbank coverage ────────────────────────────────────────────────────
// Regression guard for the dead-band bug: mel points used to be floored to
// integer FFT bins, so at 44.1/48 kHz adjacent low points collapsed onto the
// same bin and produced all-zero filters. Those bands read -120 dB forever and
// showed up as permanent black stripes. Android routinely ignores the requested
// 16 kHz, so the non-16k rates are the ones that matter.
(() => {
  console.log('\n-- mel filterbank coverage --');
  const RATES = [16000, 44100, 48000];
  // The display runs at whatever rate the device hands back, so it must be clean
  // at all three. The CNN geometry (128 mels) is only ever fed 16 kHz, matching
  // features.py — at 48 kHz the narrowest mel band (46.0 Hz) is thinner than the
  // FFT bin spacing (46.9 Hz), which no filterbank can resolve. librosa produces
  // exactly one empty filter for that same config. Asserted separately below as
  // a *detected* condition rather than pretended away.
  const CONFIGS = [
    { nMels: spec.MEL_DISPLAY, label: 'display', rates: RATES },
    { nMels: 128, label: 'CNN', rates: [16000] },
  ];

  const observedDead = (s, nMels, sr) => {
    const noise = new Float32Array(sr);
    for (let i = 0; i < noise.length; i++) noise[i] = Math.random() * 2 - 1;
    const cols = s.push(noise);
    const peak = new Float32Array(nMels);
    for (const c of cols) for (let m = 0; m < nMels; m++) if (c[m] > peak[m]) peak[m] = c[m];
    const dead = [];
    for (let m = 0; m < nMels; m++) if (peak[m] === 0) dead.push(m);
    return { cols, dead };
  };

  for (const { nMels, label, rates } of CONFIGS) {
    for (const sr of rates) {
      const s = new spec.MelSpectrogramStreamer(nMels, sr);
      const { cols, dead } = observedDead(s, nMels, sr);
      ok(cols.length > 0, `${label} ${sr}Hz: produced ${cols.length} columns`);
      ok(dead.length === 0,
         `${label} ${sr}Hz: no permanently-black mel band` +
         (dead.length ? ` (dead: ${dead.slice(0, 10).join(',')}${dead.length > 10 ? '…' : ''})` : ''));
      ok(s.deadBands.length === 0,
         `${label} ${sr}Hz: streamer reports no dead bands`);
    }
  }

  // Under-resolved config: the streamer must NOTICE, and what it reports must
  // match what the audio actually shows. A silent black stripe is the bug; a
  // declared one is a documented limit.
  {
    const s = new spec.MelSpectrogramStreamer(128, 48000);
    const { dead } = observedDead(s, 128, 48000);
    ok(s.deadBands.length > 0,
       `CNN 128 mels @48kHz: under-resolution is detected (deadBands=[${s.deadBands.join(',')}])`);
    ok(JSON.stringify(s.deadBands) === JSON.stringify(dead),
       `CNN 128 mels @48kHz: reported dead bands match the observed silent ones ` +
       `(reported [${s.deadBands}], observed [${dead}])`);
  }

  // Unit-height triangles are what make SPEC_DB_FLOOR/CEIL absolute dBFS: a
  // full-scale tone must read ~0 dBFS in whichever band it lands in, at any rate.
  const toDb = v => spec.SPEC_DB_FLOOR + v * (spec.SPEC_DB_CEIL - spec.SPEC_DB_FLOOR);
  for (const sr of RATES) {
    const s = new spec.MelSpectrogramStreamer(spec.MEL_DISPLAY, sr);
    const n = Math.floor(sr * 0.5), tone = new Float32Array(n);
    for (let i = 0; i < n; i++) tone[i] = Math.sin((2 * Math.PI * 1000 * i) / sr);
    const cols = s.push(tone);
    const db = toDb(Math.max(...cols[cols.length - 1]));
    ok(Math.abs(db) <= 3.0, `${sr}Hz: full-scale 1kHz tone reads ${db.toFixed(1)} dBFS (want ~0)`);
  }

  // Silence must stay at the floor — the bug this file's constants comment
  // describes was silence rendering as full brightness.
  for (const sr of RATES) {
    const s = new spec.MelSpectrogramStreamer(spec.MEL_DISPLAY, sr);
    const cols = s.push(new Float32Array(Math.floor(sr * 0.2)));
    const worst = Math.max(...cols[cols.length - 1]);
    ok(worst === 0, `${sr}Hz: digital silence stays at 0.0 (got ${worst})`);
  }
})();

// ── live denoising (raw vs cleaned panels) ─────────────────────────────────────
// The cleaned panel is only worth showing if it removes the AC/fan floor while
// leaving the snore alone. Anything that dims both equally is just a darker
// picture, and anything that dims the snore is actively misleading.
(() => {
  console.log('\n-- live denoise (raw vs cleaned) --');
  const dn = loadTs(path.join(ML, 'denoise.ts'));
  const sr = spec.SR;

  // Snore bursts over a stationary AC hum + broadband fan hiss — the scene the
  // `safe` preset was tuned against.
  const dur = 12;
  const n = sr * dur;
  const sig = new Float32Array(n);
  const isSnore = new Uint8Array(n);
  let seed = 12345;
  const rnd = () => { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff * 2 - 1; };
  for (let i = 0; i < n; i++) {
    const t = i / sr;
    sig[i] = 0.030 * Math.sin(2 * Math.PI * 50 * t)      // mains hum
           + 0.015 * Math.sin(2 * Math.PI * 100 * t)
           + 0.010 * rnd();                              // fan hiss (broadband)
  }
  for (let start = 3.0; start < dur - 2; start += 4.0) {
    const i0 = Math.floor(start * sr), i1 = Math.floor((start + 1.5) * sr);
    for (let i = i0; i < i1; i++) {
      const s = (i - i0) / (i1 - i0);
      const env = Math.sin(Math.PI * s) ** 2;
      const tt = (i - i0) / sr;
      sig[i] += env * (0.30 * Math.sin(2 * Math.PI * 200 * tt)
                     + 0.15 * Math.sin(2 * Math.PI * 400 * tt)
                     + 0.08 * Math.sin(2 * Math.PI * 600 * tt));
      isSnore[i] = 1;
    }
  }

  const s = new spec.MelSpectrogramStreamer(spec.MEL_DISPLAY, sr);
  const { raw, clean } = s.pushDual(sig);
  ok(raw.length === clean.length && raw.length > 0,
     `pushDual returned matched panels (${raw.length} columns each)`);
  ok(s.denoiseReady, 'noise floor warmed up over the clip');

  // Label each column by whether its centre sample was inside a snore burst.
  const HOP = 512;
  const snoreCols = [], gapCols = [];
  for (let c = 0; c < raw.length; c++) {
    const centre = c * HOP + 512;
    (isSnore[Math.min(centre, n - 1)] ? snoreCols : gapCols).push(c);
  }
  // Ignore warm-up columns; the tracker passes audio through untouched there.
  const settled = c => c >= 60;
  const mean = (cols, panel) => {
    let sum = 0, cnt = 0;
    for (const c of cols) if (settled(c))
      for (let m = 0; m < spec.MEL_DISPLAY; m++) { sum += panel[c][m]; cnt++; }
    return cnt ? sum / cnt : NaN;
  };
  const peak = (cols, panel) => {
    let mx = 0;
    for (const c of cols) if (settled(c))
      for (let m = 0; m < spec.MEL_DISPLAY; m++) if (panel[c][m] > mx) mx = panel[c][m];
    return mx;
  };

  const span = spec.SPEC_DB_CEIL - spec.SPEC_DB_FLOOR;
  const gapRaw = mean(gapCols, raw), gapClean = mean(gapCols, clean);
  const snPeakRaw = peak(snoreCols, raw), snPeakClean = peak(snoreCols, clean);
  const gapDropDb = (gapRaw - gapClean) * span;
  const snoreLossDb = (snPeakRaw - snPeakClean) * span;

  console.log(`       background between snores: ${(gapRaw * span + spec.SPEC_DB_FLOOR).toFixed(1)}`
            + ` -> ${(gapClean * span + spec.SPEC_DB_FLOOR).toFixed(1)} dB  (down ${gapDropDb.toFixed(1)} dB)`);
  console.log(`       snore peak:                ${(snPeakRaw * span + spec.SPEC_DB_FLOOR).toFixed(1)}`
            + ` -> ${(snPeakClean * span + spec.SPEC_DB_FLOOR).toFixed(1)} dB  (down ${snoreLossDb.toFixed(1)} dB)`);

  ok(gapDropDb > 6, `background floor pushed down by ${gapDropDb.toFixed(1)} dB (want >6)`);
  ok(snoreLossDb < 3, `snore peak preserved within ${snoreLossDb.toFixed(1)} dB (want <3)`);
  ok(gapDropDb > snoreLossDb * 3,
     `cleaning is selective, not a global dim (${gapDropDb.toFixed(1)} dB vs ${snoreLossDb.toFixed(1)} dB)`);

  // Raw panel must be untouched by the denoiser — same numbers push() gives.
  const s2 = new spec.MelSpectrogramStreamer(spec.MEL_DISPLAY, sr);
  const only = s2.push(sig);
  let identical = only.length === raw.length;
  if (identical) outer: for (let c = 0; c < only.length; c++)
    for (let m = 0; m < spec.MEL_DISPLAY; m++)
      if (Math.abs(only[c][m] - raw[c][m]) > 1e-9) { identical = false; break outer; }
  ok(identical, 'pushDual raw panel is bit-identical to push()');

  // Tracker behaviour: a loud burst must not be learned as noise.
  {
    const t = new dn.NoiseFloorTracker();
    const quiet = new Float32Array(64).fill(0.001);
    for (let i = 0; i < 200; i++) t.update(quiet);
    const settledFloor = t.estimate[0];
    const loud = new Float32Array(64).fill(1.0);
    for (let i = 0; i < 40; i++) t.update(loud);
    const afterBurst = t.estimate[0];
    ok(afterBurst < settledFloor * 10,
       `40 loud frames barely move the floor (${settledFloor.toExponential(1)} -> ${afterBurst.toExponential(1)})`);
    for (let i = 0; i < 200; i++) t.update(quiet);
    ok(t.estimate[0] < settledFloor * 2, 'floor recovers once the burst passes');
  }

  // Before warm-up, nothing should be subtracted.
  {
    const t = new dn.NoiseFloorTracker();
    const p = Float32Array.from({ length: 8 }, (_, i) => (i + 1) * 0.1);
    t.update(p);
    const out = new Float32Array(8);
    const binHz = Float64Array.from({ length: 8 }, (_, i) => 200 + i * 100);
    dn.spectralSubtract(p, t, binHz, dn.DENOISE_DEFAULTS, out);
    let same = true;
    for (let i = 0; i < 8; i++) if (out[i] !== p[i]) same = false;
    ok(same, 'passes audio through unchanged until the floor estimate is ready');
  }
})();

console.log(failures ? `\n${failures} check(s) FAILED` : '\nALL CHECKS PASSED');
process.exit(failures ? 1 : 0);
