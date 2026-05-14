"""
XGBoost snore intensity regressor (FR-ML-003).

Production: XGBRegressor trained on 40 MFCCs + delta + prosodic features.
Dev / test: RMS-energy-based stub — no model file required.
"""
import logging

import numpy as np

_logger = logging.getLogger(__name__)

# Index of the RMS energy feature in the 126-dim feature vector
_RMS_IDX = 120


class IntensityRegressor:
    """
    Accepts a 126-dim feature vector (output of features.extract_features).
    Returns a snore intensity score in [0.0, 100.0].
    """

    def __init__(self):
        self._model  = None
        self.is_stub = True

    # ── Model loading ──────────────────────────────────────────────────────────

    def load(self, model_path: str) -> bool:
        try:
            import xgboost as xgb
            self._model = xgb.XGBRegressor()
            self._model.load_model(model_path)
            self.is_stub = False
            _logger.info("Loaded intensity regressor from %s", model_path)
            return True
        except Exception as exc:
            _logger.warning("Could not load regressor (%s) — using stub", exc)
            return False

    # ── Inference ──────────────────────────────────────────────────────────────

    def predict(self, features: np.ndarray) -> float:
        """Return intensity ∈ [0.0, 100.0]."""
        if self.is_stub:
            return self._stub_predict(features)
        raw = float(self._model.predict(features.reshape(1, -1))[0])
        return round(float(np.clip(raw, 0.0, 100.0)), 1)

    # ── Stub ───────────────────────────────────────────────────────────────────

    def _stub_predict(self, features: np.ndarray) -> float:
        """
        Linear mapping from RMS energy (feature[120]) → intensity 0-100.
        Calibrated so a sine wave at half amplitude maps to ~50.
        """
        rms = float(features[_RMS_IDX]) if len(features) > _RMS_IDX else float(np.mean(np.abs(features)))
        intensity = min(100.0, max(0.0, rms * 200.0))
        return round(intensity, 1)
