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

// transpile a TS module in-memory (no type-check) and load it as CommonJS
function loadTs(srcPath) {
  const js = ts.transpileModule(fs.readFileSync(srcPath, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2019, esModuleInterop: true },
  }).outputText;
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

console.log(failures ? `\n${failures} check(s) FAILED` : '\nALL CHECKS PASSED');
process.exit(failures ? 1 : 0);
