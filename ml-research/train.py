"""
SleepSense — Snore Classifier Training (local CPU run)

Usage:
    python ml-research/train.py

Saves checkpoints every epoch → safe to Ctrl+C and resume.
To resume: python ml-research/train.py --resume

Data protocol (leakage-free — see src/data_prep.py + tests/test_data_prep.py):
    * canonical ESC-50 fold split: train=folds 1-3, val=fold 4, test=fold 5
    * breathing = ESC-50 target 23 (real breathing clips)
    * oversampling (snoring/breathing ×6) + augmentation on the TRAIN fold only
    * checkpoint/early-stop on val macro-F1, not accuracy (ambient-majority bias)

Output:
    ml-research/output/best_model.keras       ← best val macro-F1
    ml-research/output/snore_classifier.tflite ← quantized for mobile
    ml-research/output/training_history.png   ← loss/accuracy curves
"""
import os, sys, json, random, argparse, warnings
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
import numpy as np
import pandas as pd
import librosa, soundfile as sf, cv2
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers, callbacks
from sklearn.metrics import classification_report, f1_score, confusion_matrix
import matplotlib; matplotlib.use('Agg')  # no display needed
import matplotlib.pyplot as plt
import seaborn as sns
import urllib.request, zipfile

warnings.filterwarnings('ignore')
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'

tf.random.set_seed(42)
np.random.seed(42)
random.seed(42)

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT       = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from src.data_prep import (LABEL_SNORING, LABEL_BREATHING,  # noqa: E402
                           build_esc50_records, make_silence_records,
                           generate_silence_clip, split_by_fold,
                           oversample_with_augment)
from src.train_utils import MacroF1Checkpoint  # noqa: E402

DATA_DIR   = os.path.join(ROOT, 'data')
# v2: fold-based leakage-free splits — the old data/spectrograms cache mixes
# augmented duplicates across splits and has the wrong breathing labels.
SPEC_DIR   = os.path.join(DATA_DIR, 'spectrograms_v2')
MODEL_DIR  = os.path.join(ROOT, 'output')
for d in [DATA_DIR, SPEC_DIR, MODEL_DIR]:
    os.makedirs(d, exist_ok=True)

# ── Hyperparameters ───────────────────────────────────────────────────────────
SAMPLE_RATE  = 16_000
WINDOW_SEC   = 3.0
N_MELS       = 128
N_FFT        = 1024
HOP_LENGTH   = 512
F_MIN        = 50
F_MAX        = 8_000
IMG_SIZE     = 128
TOP_DB       = 80.0
CLASSES      = ['snoring', 'breathing', 'silence', 'ambient']
N_CLASSES    = len(CLASSES)
BATCH_SIZE   = 16    # conservative for CPU RAM
EPOCHS_HEAD  = 5
EPOCHS_FINE  = 20
LR_HEAD      = 1e-3
LR_FINE      = 1e-4


# ── Audio utilities ───────────────────────────────────────────────────────────

def load_audio(path, offset=0.0):
    y, _ = librosa.load(path, sr=SAMPLE_RATE, mono=True,
                        offset=offset, duration=WINDOW_SEC)
    target = int(SAMPLE_RATE * WINDOW_SEC)
    if len(y) < target:
        y = np.pad(y, (0, target - len(y)))
    return y[:target].astype(np.float32)


def audio_to_melspec(y):
    mel = librosa.feature.melspectrogram(
        y=y, sr=SAMPLE_RATE, n_fft=N_FFT, hop_length=HOP_LENGTH,
        n_mels=N_MELS, fmin=F_MIN, fmax=F_MAX)
    log_mel = librosa.power_to_db(mel, ref=1.0, top_db=TOP_DB)
    img = cv2.resize(log_mel, (IMG_SIZE, IMG_SIZE), interpolation=cv2.INTER_LINEAR)
    img = (img - img.min()) / (img.max() - img.min() + 1e-8)
    return img.astype(np.float32)


def augment(y):
    if random.random() < 0.5:
        y = librosa.effects.time_stretch(y, rate=random.uniform(0.85, 1.15))
    if random.random() < 0.5:
        y = librosa.effects.pitch_shift(y, sr=SAMPLE_RATE, n_steps=random.uniform(-2, 2))
    if random.random() < 0.4:
        y = y + (np.random.randn(len(y)) * random.uniform(0.001, 0.01)).astype(np.float32)
    if random.random() < 0.3:
        y = y * (10 ** (random.uniform(-6, 6) / 20))
    target = int(SAMPLE_RATE * WINDOW_SEC)
    if len(y) < target:
        y = np.pad(y, (0, target - len(y)))
    return y[:target].astype(np.float32)


# ── Dataset download ──────────────────────────────────────────────────────────

def download_esc50():
    esc50_dir = os.path.join(DATA_DIR, 'ESC-50-master')
    if os.path.exists(esc50_dir):
        print('ESC-50 already downloaded.')
        return esc50_dir
    print('Downloading ESC-50 (~600 MB)...')
    zip_path = os.path.join(DATA_DIR, 'esc50.zip')
    url = 'https://github.com/karoldvl/ESC-50/archive/master.zip'
    urllib.request.urlretrieve(url, zip_path,
        reporthook=lambda b, bs, t: print(f'\r  {min(b*bs, t)/1e6:.0f}/{t/1e6:.0f} MB', end=''))
    print()
    with zipfile.ZipFile(zip_path, 'r') as z:
        z.extractall(DATA_DIR)
    os.remove(zip_path)
    print(f'ESC-50 ready at {esc50_dir}')
    return esc50_dir


# ── Build sample list (leakage-free — logic lives in src/data_prep.py) ────────

def build_split_records(esc50_dir):
    """ESC-50 fold split (train=1-3, val=4, test=5) + silence, oversampling and
    augmentation flags applied to the TRAIN split only."""
    meta      = pd.read_csv(os.path.join(esc50_dir, 'meta', 'esc50.csv'))
    audio_dir = os.path.join(esc50_dir, 'audio')
    records   = [r for r in build_esc50_records(meta, audio_dir)
                 if os.path.exists(r.path)]

    sil_dir = os.path.join(DATA_DIR, 'silence')
    os.makedirs(sil_dir, exist_ok=True)
    sil_records = make_silence_records(sil_dir, n=400)
    for i, r in enumerate(sil_records):
        if not os.path.exists(r.path):
            sf.write(r.path, generate_silence_clip(WINDOW_SEC, SAMPLE_RATE,
                                                   rng=np.random.default_rng(i)),
                     SAMPLE_RATE)
    records += sil_records

    train, val, test = split_by_fold(records)
    train = oversample_with_augment(train, {LABEL_SNORING: 6, LABEL_BREATHING: 6})
    random.shuffle(train)
    return {'train': train, 'val': val, 'test': test}


# ── Pre-compute spectrograms (per split; augment train duplicates only) ───────

def precompute_spectrograms(splits):
    """Cache one .npy per record under SPEC_DIR/<split>/. Returns
    {split: (paths, labels)}. Augmentation is applied only where the record's
    `augment` flag is set — never on val/test."""
    out = {}
    for name, records in splits.items():
        split_dir = os.path.join(SPEC_DIR, name)
        os.makedirs(split_dir, exist_ok=True)
        done_flag = os.path.join(split_dir, 'done.json')
        if os.path.exists(done_flag):
            with open(done_flag) as f:
                info = json.load(f)
            print(f'{name}: {info["count"]} cached spectrograms. Skipping.')
            paths = [os.path.join(split_dir, f'{i:06d}.npy') for i in range(info['count'])]
            out[name] = (paths, info['labels'])
            continue

        print(f'{name}: pre-computing {len(records)} spectrograms...')
        paths, labels = [], []
        for i, r in enumerate(records):
            try:
                y = load_audio(r.path)
                if r.augment:
                    y = augment(y)
                spec = audio_to_melspec(y)
            except Exception as e:
                print(f'  skip {r.path}: {e}')
                continue
            p = os.path.join(split_dir, f'{len(paths):06d}.npy')
            np.save(p, spec)
            paths.append(p)
            labels.append(r.label)
            if (i + 1) % 200 == 0:
                print(f'  {i+1}/{len(records)}')

        with open(done_flag, 'w') as f:
            json.dump({'count': len(paths), 'labels': labels}, f)
        print(f'{name}: {len(paths)} spectrograms saved.')
        out[name] = (paths, labels)
    return out


# ── tf.data pipeline ──────────────────────────────────────────────────────────

def load_spec_tf(path, label):
    # TF 2.20: numpy_function passes args as raw bytes, not EagerTensors — use .decode() directly
    spec = tf.numpy_function(lambda p: np.load(p.decode()), [path], tf.float32)
    spec.set_shape([IMG_SIZE, IMG_SIZE])
    spec = tf.stack([spec, spec, spec], axis=-1)  # (128,128,3) for EfficientNet
    return spec, tf.cast(label, tf.int32)


def make_dataset(paths, lbls, training=False):
    ds = tf.data.Dataset.from_tensor_slices((paths, lbls))
    ds = ds.map(load_spec_tf, num_parallel_calls=tf.data.AUTOTUNE)
    if training:
        ds = ds.shuffle(1000, seed=42)
    return ds.batch(BATCH_SIZE).prefetch(tf.data.AUTOTUNE)


# ── Model ─────────────────────────────────────────────────────────────────────

def build_model(trainable_backbone=False):
    # MobileNetV2: stable with TF 2.20/Keras 3, faster on CPU than EfficientNetB0,
    # and EfficientNetB0 has a Keras 3 weight-loading bug with non-default input sizes.
    backbone = keras.applications.MobileNetV2(
        include_top=False, weights='imagenet',
        input_shape=(IMG_SIZE, IMG_SIZE, 3)
    )
    backbone.trainable = trainable_backbone

    inputs  = keras.Input(shape=(IMG_SIZE, IMG_SIZE, 3))
    # MobileNetV2 expects inputs in [-1, 1]; spectrograms are in [0, 1]
    x       = layers.Rescaling(scale=2.0, offset=-1.0)(inputs)
    x       = backbone(x, training=False)
    x       = layers.GlobalAveragePooling2D()(x)
    x       = layers.BatchNormalization()(x)
    x       = layers.Dropout(0.3)(x)
    x       = layers.Dense(256, activation='relu')(x)
    x       = layers.Dropout(0.2)(x)
    outputs = layers.Dense(N_CLASSES, activation='softmax')(x)
    return keras.Model(inputs, outputs)


# ── Plot helpers ──────────────────────────────────────────────────────────────

def plot_history(histories, out_path):
    acc  = histories[0].history['accuracy']  + histories[1].history['accuracy']
    val  = histories[0].history['val_accuracy'] + histories[1].history['val_accuracy']
    loss = histories[0].history['loss'] + histories[1].history['loss']
    vloss= histories[0].history['val_loss']  + histories[1].history['val_loss']
    ep   = range(1, len(acc)+1)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))
    ax1.plot(ep, acc, label='train'); ax1.plot(ep, val, label='val')
    ax1.axvline(EPOCHS_HEAD, ls='--', color='gray', label='fine-tune start')
    ax1.set_title('Accuracy'); ax1.legend()
    ax2.plot(ep, loss, label='train'); ax2.plot(ep, vloss, label='val')
    ax2.axvline(EPOCHS_HEAD, ls='--', color='gray')
    ax2.set_title('Loss'); ax2.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=120)
    print(f'Training curves saved to {out_path}')


def plot_confusion(y_true, y_pred, out_path):
    cm = confusion_matrix(y_true, y_pred, labels=list(range(N_CLASSES)))
    plt.figure(figsize=(6, 5))
    sns.heatmap(cm, annot=True, fmt='d', xticklabels=CLASSES, yticklabels=CLASSES, cmap='Blues')
    plt.ylabel('True'); plt.xlabel('Predicted')
    plt.tight_layout()
    plt.savefig(out_path, dpi=120)
    print(f'Confusion matrix saved to {out_path}')


# ── TFLite export ─────────────────────────────────────────────────────────────

def export_tflite(model, calib_paths, out_path):
    print('Converting to TFLite INT8...')

    def rep_dataset():
        for p in random.sample(calib_paths, min(200, len(calib_paths))):
            spec  = np.load(p)
            spec3 = np.stack([spec, spec, spec], axis=-1)[np.newaxis].astype(np.float32)
            yield [spec3]

    conv = tf.lite.TFLiteConverter.from_keras_model(model)
    conv.optimizations = [tf.lite.Optimize.DEFAULT]
    conv.representative_dataset = rep_dataset
    conv.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    conv.inference_input_type  = tf.float32
    conv.inference_output_type = tf.float32
    tflite = conv.convert()

    with open(out_path, 'wb') as f:
        f.write(tflite)
    size_mb = os.path.getsize(out_path) / 1024 / 1024
    print(f'TFLite saved: {out_path}  ({size_mb:.2f} MB)')
    return out_path


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--resume', action='store_true',
                        help='Skip data prep, load best_head.keras and go straight to fine-tune')
    parser.add_argument('--smoke', action='store_true',
                        help='Tiny subset + 1 epoch per phase — verifies the pipeline end-to-end in minutes')
    args = parser.parse_args()

    global SPEC_DIR, MODEL_DIR, EPOCHS_HEAD, EPOCHS_FINE
    if args.smoke:
        SPEC_DIR = os.path.join(DATA_DIR, 'spectrograms_smoke')
        MODEL_DIR = os.path.join(ROOT, 'output_smoke')  # never clobber real artifacts
        os.makedirs(MODEL_DIR, exist_ok=True)
        EPOCHS_HEAD = EPOCHS_FINE = 1
        print('*** SMOKE MODE: 1 epoch per phase, small subset ***')

    print(f'TensorFlow {tf.__version__}  |  CPU threads: {tf.config.threading.get_inter_op_parallelism_threads()}')

    # ── Data (fold-based split — no clip leaks across train/val/test) ────────
    esc50_dir = download_esc50()
    splits    = build_split_records(esc50_dir)
    if args.smoke:
        # Class-balanced tiny subset per split (keeps every label present).
        splits = {name: sorted(recs, key=lambda r: (r.label, r.path))[::max(1, len(recs) // 80)]
                  for name, recs in splits.items()}
    specs     = precompute_spectrograms(splits)

    X_train, y_train = specs['train']
    X_val,   y_val   = specs['val']
    X_test,  y_test  = specs['test']
    print(f'Train {len(X_train)} | Val {len(X_val)} | Test {len(X_test)}')

    train_ds = make_dataset(X_train, y_train, training=True)
    val_ds   = make_dataset(X_val,   y_val)
    test_ds  = make_dataset(X_test,  y_test)

    # ── Phase 1: train head ───────────────────────────────────────────────────
    head_ckpt = os.path.join(MODEL_DIR, 'best_head.keras')
    if args.resume and os.path.exists(head_ckpt):
        print('Resuming — loading saved head weights...')
        model = build_model(trainable_backbone=False)
        model.load_weights(head_ckpt)
        hist_head_mock = type('H', (), {'history': {'accuracy': [], 'val_accuracy': [], 'loss': [], 'val_loss': []}})()
        histories = [hist_head_mock]
    else:
        model = build_model(trainable_backbone=False)
        model.compile(optimizer=keras.optimizers.Adam(LR_HEAD),
                      loss='sparse_categorical_crossentropy', metrics=['accuracy'])
        print(f'\n── Phase 1: training head ({EPOCHS_HEAD} epochs) ──')
        hist_head = model.fit(
            train_ds, validation_data=val_ds, epochs=EPOCHS_HEAD,
            callbacks=[
                MacroF1Checkpoint(val_ds, y_val, head_ckpt),
                callbacks.ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=2, verbose=1),
            ]
        )
        histories = [hist_head]

    # ── Phase 2: fine-tune top layers ────────────────────────────────────────
    model.load_weights(head_ckpt)
    backbone = next(l for l in model.layers if isinstance(l, keras.Model))
    backbone.trainable = True
    for layer in backbone.layers[:-30]:
        layer.trainable = False

    model.compile(optimizer=keras.optimizers.Adam(LR_FINE),
                  loss='sparse_categorical_crossentropy', metrics=['accuracy'])

    fine_ckpt = os.path.join(MODEL_DIR, 'best_model.keras')
    print(f'\n── Phase 2: fine-tuning ({EPOCHS_FINE} epochs) ──')
    hist_fine = model.fit(
        train_ds, validation_data=val_ds, epochs=EPOCHS_FINE,
        callbacks=[
            # MacroF1Checkpoint must run FIRST so val_macro_f1 is in the logs
            # before EarlyStopping reads them.
            MacroF1Checkpoint(val_ds, y_val, fine_ckpt),
            callbacks.EarlyStopping(monitor='val_macro_f1', mode='max', patience=6,
                                    restore_best_weights=True, verbose=1),
        ]
    )
    histories.append(hist_fine)

    # ── Evaluate ──────────────────────────────────────────────────────────────
    model.load_weights(fine_ckpt)
    print('\n── Test set evaluation ──')
    y_pred = np.argmax(model.predict(test_ds, verbose=1), axis=1)
    f1 = f1_score(y_test, y_pred, average='macro')
    print(f'\nMacro-F1: {f1:.4f}  (target > 0.92)')
    print(classification_report(y_test, y_pred, labels=list(range(N_CLASSES)),
                                target_names=CLASSES, zero_division=0))

    plot_history(histories, os.path.join(MODEL_DIR, 'training_history.png'))
    plot_confusion(y_test, y_pred, os.path.join(MODEL_DIR, 'confusion_matrix.png'))

    # ── TFLite export ─────────────────────────────────────────────────────────
    tflite_path = export_tflite(model, list(X_train), os.path.join(MODEL_DIR, 'snore_classifier.tflite'))

    print('\n── Done ──')
    print(f'Best model  : {fine_ckpt}')
    print(f'TFLite model: {tflite_path}')
    print()
    print('Next step: copy snore_classifier.tflite to mobile/assets/models/')
    if f1 >= 0.92:
        print('✅  F1 target met!')
    else:
        print(f'⚠️  F1 = {f1:.3f} — consider adding the Kaggle snoring dataset for more snoring samples.')


if __name__ == '__main__':
    main()
