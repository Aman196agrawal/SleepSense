"""
Tests for MacroF1Checkpoint (src/train_utils.py).

Regression: training checkpointed on val_accuracy, which the ~70%-majority
ambient class dominates — the model that predicts 'ambient' everywhere looks
good. Checkpoint selection must use macro-F1 so snoring/breathing count equally.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.train_utils import MacroF1Checkpoint  # noqa: E402


class FakeModel:
    """Stands in for a keras model: scripted predictions, records saves."""

    def __init__(self, preds_per_epoch):
        self._preds = list(preds_per_epoch)
        self._epoch = 0
        self.saved_at_epochs = []

    def predict(self, ds, verbose=0):
        preds = self._preds[self._epoch]
        self._epoch += 1
        return preds

    def save(self, path):
        self.saved_at_epochs.append(self._epoch - 1)


def one_hot(labels, n=4):
    m = np.zeros((len(labels), n), dtype=np.float32)
    m[np.arange(len(labels)), labels] = 1.0
    return m


def test_saves_only_when_macro_f1_improves(tmp_path):
    y_val = np.array([0, 1, 2, 3])
    cb = MacroF1Checkpoint(val_ds=None, y_val=y_val,
                           ckpt_path=str(tmp_path / "best.keras"))
    fake = FakeModel([
        one_hot([0, 0, 0, 0]),  # epoch 0: all-ambient-style collapse, low F1
        one_hot([0, 1, 2, 3]),  # epoch 1: perfect, F1=1.0 -> save
        one_hot([0, 0, 0, 0]),  # epoch 2: regresses -> no save
    ])
    cb.set_model(fake)

    logs = [{}, {}, {}]
    for epoch in range(3):
        cb.on_epoch_end(epoch, logs=logs[epoch])

    assert fake.saved_at_epochs == [0, 1]  # first epoch always beats -inf
    assert logs[1]["val_macro_f1"] == 1.0
    assert logs[2]["val_macro_f1"] < 1.0
    assert cb.best_f1 == 1.0
