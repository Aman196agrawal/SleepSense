"""
CNN snore classifier (FR-ML-002).

Production: EfficientNet-B0 fine-tuned on AudioSet, loaded from S3.
Dev / test: deterministic energy-based stub — no model file required.
"""
import logging
from typing import List

import numpy as np

_logger = logging.getLogger(__name__)
CLASSES = ["snoring", "breathing", "silence", "ambient"]


class SnoreClassifier:
    """
    Accepts a list of (128, 128) mel spectrograms.
    Returns one prediction dict per window:
      {dominant_class, confidence, probabilities: {class: float}}
    """

    def __init__(self):
        self._model   = None
        self.is_stub  = True

    # ── Model loading ──────────────────────────────────────────────────────────

    def load(self, model_path: str) -> bool:
        """Attempt to load a PyTorch model. Falls back to stub on failure."""
        try:
            import torch
            # weights_only=True prevents arbitrary code execution if the model file
            # is tampered with (e.g. replaced in S3). Load state_dict separately.
            state = torch.load(model_path, map_location="cpu", weights_only=True)
            if isinstance(state, dict):
                # Caller stored just the state_dict — build model skeleton first
                from torchvision.models import efficientnet_b0
                import torch.nn as nn
                net = efficientnet_b0()
                net.classifier[1] = nn.Linear(net.classifier[1].in_features, len(CLASSES))
                net.load_state_dict(state)
                self._model = net
            else:
                self._model = state
            self._model.eval()
            self.is_stub = False
            _logger.info("Loaded snore classifier from %s", model_path)
            return True
        except Exception as exc:
            _logger.warning("Could not load classifier (%s) — using stub", exc)
            return False

    # ── Inference ──────────────────────────────────────────────────────────────

    def predict(self, spectrograms: List[np.ndarray]) -> List[dict]:
        if self.is_stub:
            return [self._stub_predict(s) for s in spectrograms]
        return self._torch_predict(spectrograms)

    # ── Stub ───────────────────────────────────────────────────────────────────

    def _stub_predict(self, spec: np.ndarray) -> dict:
        """
        Maps mean absolute spectrogram energy → class probabilities.
        Thresholds are calibrated to produce realistic class distributions
        on typical sleep-audio spectrograms.
        """
        energy = float(np.mean(np.abs(spec)))
        if energy > 0.35:
            probs = [0.72, 0.18, 0.05, 0.05]   # high energy → snoring
        elif energy > 0.15:
            probs = [0.15, 0.65, 0.15, 0.05]   # medium     → breathing
        elif energy > 0.05:
            probs = [0.05, 0.20, 0.68, 0.07]   # low        → silence
        else:
            probs = [0.02, 0.08, 0.85, 0.05]   # very low   → silence
        dominant = int(np.argmax(probs))
        return {
            "dominant_class": CLASSES[dominant],
            "confidence":     round(probs[dominant], 3),
            "probabilities":  {c: round(p, 3) for c, p in zip(CLASSES, probs)},
        }

    # ── PyTorch model ──────────────────────────────────────────────────────────

    def _torch_predict(self, spectrograms: List[np.ndarray]) -> List[dict]:
        import torch
        results = []
        for spec in spectrograms:
            tensor = torch.tensor(spec).unsqueeze(0).unsqueeze(0)   # (1,1,128,128)
            with torch.no_grad():
                logits = self._model(tensor)
                probs  = torch.softmax(logits, dim=-1).squeeze().tolist()
            dominant = int(np.argmax(probs))
            results.append({
                "dominant_class": CLASSES[dominant],
                "confidence":     round(probs[dominant], 3),
                "probabilities":  {c: round(p, 3) for c, p in zip(CLASSES, probs)},
            })
        return results
