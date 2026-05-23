/**
 * On-device snore classifier using TensorFlow Lite (FR-ML-005).
 *
 * Model spec:
 *   Architecture : EfficientNet-B0 fine-tuned on AudioSet
 *   Input        : [1, 128, 128, 1] float32 — normalised mel spectrogram (3 s window)
 *   Output       : [1, 4] float32 — logits for [snoring, breathing, silence, ambient]
 *   Quantisation : INT8, target size <5 MB
 *   Asset path   : mobile/assets/models/snore_classifier.tflite
 *
 * In Expo Go the native module is not linked — the classifier auto-degrades to
 * a lightweight heuristic so Privacy Mode still provides real-time feedback.
 * In EAS development / production builds the TFLite model runs natively.
 */

import { buildFeaturesFromMetering } from './audioFeatures';

export type OnDeviceResult = {
  dominantClass: 'snoring' | 'breathing' | 'silence' | 'ambient';
  confidence: number;  // 0–1
  intensity: number;   // 0–100
};

type ClassName = OnDeviceResult['dominantClass'];

// Class index mapping must match the order used during model training
const CLASS_NAMES: ClassName[] = ['snoring', 'breathing', 'silence', 'ambient'];

export class OnDeviceClassifier {
  private _model: any  = null;
  private _ready       = false;

  get ready(): boolean { return this._ready; }

  /**
   * Load the bundled TFLite model.
   * Safe to call multiple times — subsequent calls are no-ops if already loaded.
   * Returns true on success, false if the native module or model is unavailable.
   */
  async load(): Promise<boolean> {
    if (this._ready) return true;
    try {
      // Dynamic require bypasses Expo Go's missing-native-module check at bundle
      // time; the try/catch handles the runtime MODULE_NOT_FOUND error cleanly.
      // eslint-disable-next-line @typescript-eslint/no-var-requires
      const tflite = require('react-native-fast-tflite');
      this._model = await tflite.loadTensorflowModel(
        // eslint-disable-next-line @typescript-eslint/no-var-requires
        require('../../assets/models/snore_classifier.tflite'),
      );
      this._ready = true;
      console.info('[OnDevice] TFLite snore classifier loaded successfully');
      return true;
    } catch (err) {
      this._ready = false;
      console.info('[OnDevice] TFLite unavailable — heuristic fallback active:', err);
      return false;
    }
  }

  /**
   * Classify from raw metering history (the always-available path in managed workflow).
   * Internally builds the feature vector then runs the model (or heuristic fallback).
   */
  classifyFromMetering(meteringHistory: number[]): OnDeviceResult {
    const features = buildFeaturesFromMetering(meteringHistory);
    return this.classifyFromFeatures(features);
  }

  /**
   * Classify from a pre-built 128×128 feature vector (Float32Array of length 16 384).
   * Use this when PCM samples are available and you computed a real mel spectrogram.
   */
  classifyFromFeatures(features: Float32Array): OnDeviceResult {
    if (!this._ready || !this._model) {
      return _heuristicFromFeatures(features);
    }
    try {
      const outputs: Float32Array[] = this._model.runSync([features]);
      const logits  = outputs[0];
      const probs   = _softmax(logits);
      const topIdx  = _argmax(probs);
      return {
        dominantClass: CLASS_NAMES[topIdx],
        confidence:    probs[topIdx],
        intensity:     Math.round(probs[0] * 100), // snoring probability → intensity
      };
    } catch (err) {
      console.warn('[OnDevice] Inference error — heuristic fallback:', err);
      return _heuristicFromFeatures(features);
    }
  }
}

// ── Module-level singleton ────────────────────────────────────────────────────
// One instance shared across the app lifetime; load() is idempotent.
export const onDeviceClassifier = new OnDeviceClassifier();

// ── Pure helpers ──────────────────────────────────────────────────────────────

function _softmax(arr: Float32Array): number[] {
  const max  = Math.max(...arr);
  const exps = Array.from(arr).map(v => Math.exp(v - max));
  const sum  = exps.reduce((a, b) => a + b, 0);
  return exps.map(e => e / sum);
}

function _argmax(arr: number[]): number {
  return arr.reduce((best, v, i) => (v > arr[best] ? i : best), 0);
}

/** Energy-based heuristic using mean feature magnitude — used when model is absent. */
function _heuristicFromFeatures(features: Float32Array): OnDeviceResult {
  const mean      = features.reduce((s, v) => s + Math.abs(v), 0) / features.length;
  const intensity = Math.min(100, Math.round(mean * 200));
  const cls: ClassName =
    intensity < 8  ? 'silence'   :
    intensity < 30 ? 'breathing' :
                     'snoring';
  return { dominantClass: cls, confidence: 0.6, intensity };
}
