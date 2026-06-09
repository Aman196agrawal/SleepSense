/**
 * Audio feature extraction for on-device inference (FR-ML-005).
 *
 * FULL PATH (production): raw PCM → DC removal → peak-normalise → STFT →
 *   mel filter bank (128 bins) → log-compress → 128×128 spectrogram.
 *   Implement this via a WASM-based DSP library or a custom native module
 *   when PCM access is available (bare/ejected workflow).
 *
 * APPROXIMATION (managed workflow): expo-audio metering gives one dBFS
 *   reading every 200 ms. We map the recent TIME_FRAMES readings onto a
 *   128×128 pseudo-spectrogram using a simplified mel-filter shape so the
 *   tensor has the correct shape for the model even without raw PCM.
 *   Accuracy is lower than the cloud CNN but sufficient for real-time
 *   on-device feedback in Privacy Mode.
 */

export const MEL_BINS    = 128;
export const TIME_FRAMES = 128;

const DB_FLOOR = -80; // dBFS silence floor
const DB_CEIL  =   0; // dBFS maximum

/**
 * Build a [TIME_FRAMES × MEL_BINS] pseudo-mel-spectrogram from metering history.
 * Returns a Float32Array of length 128*128 = 16 384, values in [-1, 1].
 *
 * @param meteringHistory  Recent dBFS readings from expo-audio (newest last).
 */
export function buildFeaturesFromMetering(meteringHistory: number[]): Float32Array {
  const features = new Float32Array(TIME_FRAMES * MEL_BINS);

  // Pad front with silence if we have fewer than TIME_FRAMES readings
  const padded = new Float32Array(TIME_FRAMES).fill(DB_FLOOR);
  const src = meteringHistory.slice(-TIME_FRAMES);
  for (let i = 0; i < src.length; i++) {
    padded[TIME_FRAMES - src.length + i] = src[i];
  }

  for (let t = 0; t < TIME_FRAMES; t++) {
    const db     = Math.max(DB_FLOOR, Math.min(DB_CEIL, padded[t]));
    const energy = (db - DB_FLOOR) / (DB_CEIL - DB_FLOOR); // [0, 1]

    for (let m = 0; m < MEL_BINS; m++) {
      // Snoring energy concentrates in low-mid mel bins (~100–500 Hz).
      // Modelling this as a Gaussian centred at bin 25 (≈200 Hz equivalent).
      const melWeight = _melFilter(m, energy);
      features[t * MEL_BINS + m] = melWeight * 2 - 1; // map to [-1, 1]
    }
  }

  return features;
}

/** Gaussian mel-filter response — higher energy in low-mid bins. */
function _melFilter(binIndex: number, energy: number): number {
  const peak  = 25;
  const width = 30;
  const shape = Math.exp(-((binIndex - peak) ** 2) / (2 * width ** 2));
  return Math.min(1, energy * (0.35 + shape * 0.65));
}
