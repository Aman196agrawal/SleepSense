"""
Training utilities for the snore classifier.

MacroF1Checkpoint replaces `ModelCheckpoint(monitor='val_accuracy')`: with a
~70%-majority ambient class, val accuracy rewards collapsing to 'ambient'.
Macro-F1 weights snoring/breathing/silence/ambient equally, which is what the
product actually needs (snoring recall is the point of the app).
"""
from __future__ import annotations

import numpy as np
from sklearn.metrics import f1_score
from tensorflow import keras


class MacroF1Checkpoint(keras.callbacks.Callback):
    """Compute macro-F1 on the validation set each epoch; save the model when
    it improves. Adds 'val_macro_f1' to the epoch logs so EarlyStopping and
    history plots can use it."""

    def __init__(self, val_ds, y_val, ckpt_path: str):
        super().__init__()
        self.val_ds = val_ds
        self.y_val = np.asarray(y_val)
        self.ckpt_path = ckpt_path
        self.best_f1 = -np.inf

    def on_epoch_end(self, epoch, logs=None):
        y_pred = np.argmax(self.model.predict(self.val_ds, verbose=0), axis=1)
        f1 = float(f1_score(self.y_val, y_pred, average="macro"))
        if logs is not None:
            logs["val_macro_f1"] = f1
        if f1 > self.best_f1:
            self.best_f1 = f1
            self.model.save(self.ckpt_path)
            print(f"\n[MacroF1Checkpoint] val_macro_f1={f1:.4f} — saved {self.ckpt_path}")
        else:
            print(f"\n[MacroF1Checkpoint] val_macro_f1={f1:.4f} (best {self.best_f1:.4f})")
