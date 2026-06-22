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
            # weights_only=True hardens against pickle code execution, so torch.load
            # always returns a state_dict (never a full pickled Module) — build the
            # skeleton and load weights into it.
            state = torch.load(model_path, map_location="cpu", weights_only=True)
            from torchvision.models import efficientnet_b0
            import torch.nn as nn
            net = efficientnet_b0()
            net.classifier[1] = nn.Linear(net.classifier[1].in_features, len(CLASSES))
            net.load_state_dict(state)
            self._model = net
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
        if not spectrograms:
            return []
        # Stack into a single (N, 3, 128, 128) batch. efficientnet_b0's stem conv
        # expects 3 channels, so replicate the single mel channel across all three.
        batch = torch.tensor(np.stack(spectrograms)).unsqueeze(1).repeat(1, 3, 1, 1)
        with torch.no_grad():
            logits = self._model(batch)                       # (N, num_classes)
            probs_batch = torch.softmax(logits, dim=-1).tolist()
        results = []
        for probs in probs_batch:
            dominant = int(np.argmax(probs))
            results.append({
                "dominant_class": CLASSES[dominant],
                "confidence":     round(probs[dominant], 3),
                "probabilities":  {c: round(p, 3) for c, p in zip(CLASSES, probs)},
            })
        return results
