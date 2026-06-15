"""
SleepSense — Snore Classifier Training (CPU-optimised)
=======================================================
Model   : MobileNetV2 (ImageNet weights, frozen backbone → fine-tune top layers)
Input   : 128×128 log-mel spectrogram, 3-second window, 3-channel (replicated)
Classes : snoring / breathing / silence / ambient
Data    : ESC-50 (already in ml-research/data/ESC-50-master/)
Output  : mobile/assets/models/snore_classifier.tflite  (INT8 quantised)

Run from the repo root:
    python ml-research/train_cpu.py

Estimated time on a mid-range laptop CPU:
    Preprocessing  : ~10 min
    Phase 1 (head) : ~1–2 h   (5 epochs, backbone frozen)
    Phase 2 (fine) : ~4–8 h   (15 epochs, top 30 layers unfrozen)
"""

import os, sys, random, warnings, json, time
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
import numpy as np
import pandas as pd
import librosa
import soundfile as sf
import cv2
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers, callbacks
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, f1_score, confusion_matrix
import matplotlib
matplotlib.use('Agg')          # headless — saves plots to disk instead of opening a window
import matplotlib.pyplot as plt

warnings.filterwarnings('ignore')
tf.random.set_seed(42)
np.random.seed(42)
random.seed(42)

# ── Paths ─────────────────────────────────────────────────────────────────────

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT    = os.path.dirname(SCRIPT_DIR)

ESC50_DIR    = os.path.join(SCRIPT_DIR, 'data', 'ESC-50-master')
SILENCE_DIR  = os.path.join(SCRIPT_DIR, 'data', 'silence')
# Spectrograms go in system temp (outside OneDrive) to avoid sync-lock conflicts
SPEC_DIR     = os.path.join(os.environ.get('TEMP', os.path.expanduser('~')), 'sleepsense_specs')
MODEL_DIR    = os.path.join(SCRIPT_DIR, 'models')
TFLITE_OUT   = os.path.join(REPO_ROOT, 'mobile', 'assets', 'models', 'snore_classifier.tflite')

for d in [SILENCE_DIR, SPEC_DIR, MODEL_DIR]:
    os.makedirs(d, exist_ok=True)

print(f'TensorFlow {tf.__version__}')
print(f'GPU detected: {len(tf.config.list_physical_devices("GPU")) > 0}')
print(f'ESC-50 path : {ESC50_DIR}')

if not os.path.exists(os.path.join(ESC50_DIR, 'meta', 'esc50.csv')):
    print('\nERROR: ESC-50 not found. Expected: ml-research/data/ESC-50-master/meta/esc50.csv')
    sys.exit(1)

# ── Constants ─────────────────────────────────────────────────────────────────

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
N_CLASSES    = 4

# ESC-50 numeric labels
ESC50_SNORING   = 28   # "Snoring"
ESC50_BREATHING = 23   # "Breathing"
# Everything else → ambient

BATCH_SIZE    = 16     # CPU-safe (was 32 in Colab version)
EPOCHS_HEAD   = 5      # Phase 1: frozen backbone
EPOCHS_FINE   = 15     # Phase 2: top 30 layers unfrozen
LR_HEAD       = 1e-3
LR_FINE       = 5e-5

# ── Audio helpers ─────────────────────────────────────────────────────────────

def load_audio(path: str, offset: float = 0.0) -> np.ndarray:
    y, _ = librosa.load(path, sr=SAMPLE_RATE, mono=True,
                        offset=offset, duration=WINDOW_SEC)
    target = int(SAMPLE_RATE * WINDOW_SEC)
    if len(y) < target:
        y = np.pad(y, (0, target - len(y)))
    return y[:target].astype(np.float32)


def audio_to_melspec(y: np.ndarray) -> np.ndarray:
    mel = librosa.feature.melspectrogram(
        y=y, sr=SAMPLE_RATE, n_fft=N_FFT, hop_length=HOP_LENGTH,
        n_mels=N_MELS, fmin=F_MIN, fmax=F_MAX
    )
    log_mel = librosa.power_to_db(mel, ref=1.0, top_db=TOP_DB)
    img = cv2.resize(log_mel, (IMG_SIZE, IMG_SIZE), interpolation=cv2.INTER_LINEAR)
    img = (img - img.min()) / (img.max() - img.min() + 1e-8)
    return img.astype(np.float32)   # (128, 128)


def generate_silence() -> np.ndarray:
    rms   = 10 ** (-45 / 20)
    noise = np.random.randn(int(SAMPLE_RATE * WINDOW_SEC)).astype(np.float32)
    return noise / (noise.std() + 1e-9) * rms


def augment(y: np.ndarray) -> np.ndarray:
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

# ── 1. Build sample list ──────────────────────────────────────────────────────

print('\n── Step 1: Building sample list ──────────────────────────────────────')

meta      = pd.read_csv(os.path.join(ESC50_DIR, 'meta', 'esc50.csv'))
audio_dir = os.path.join(ESC50_DIR, 'audio')

records = []   # (path, label, do_augment)

for _, row in meta.iterrows():
    fpath = os.path.join(audio_dir, row['filename'])
    if not os.path.exists(fpath):
        continue
    t = row['target']
    if t == ESC50_SNORING:
        for _ in range(6):           # oversample ×6 (only 40 clips)
            records.append((fpath, 0, True))
    elif t == ESC50_BREATHING:
        for _ in range(6):           # oversample ×6 (only 40 clips)
            records.append((fpath, 1, True))
    else:
        records.append((fpath, 3, False))   # ambient

# Generate silence samples
print(f'Generating 400 silence samples...')
for i in range(400):
    sp = os.path.join(SILENCE_DIR, f'sil_{i:04d}.wav')
    if not os.path.exists(sp):
        sf.write(sp, generate_silence(), SAMPLE_RATE)
    records.append((sp, 2, False))

random.shuffle(records)
df = pd.DataFrame(records, columns=['path', 'label', 'do_augment'])

label_counts = df['label'].map({i: c for i, c in enumerate(CLASSES)}).value_counts()
print(f'Total samples: {len(df)}')
for cls, cnt in label_counts.items():
    print(f'  {cls:12s}: {cnt}')

# ── 2. Pre-compute spectrograms ───────────────────────────────────────────────

print('\n── Step 2: Pre-computing spectrograms (this takes ~10 min) ───────────')
t0 = time.time()

spec_paths, labels = [], []
skipped = 0

for i, row in df.iterrows():
    out = os.path.join(SPEC_DIR, f'{i:06d}.npy')

    if os.path.exists(out):
        spec_paths.append(out)
        labels.append(row['label'])
        continue

    try:
        y = load_audio(row['path'])
        if row['do_augment']:
            y = augment(y)
        spec = audio_to_melspec(y)
    except Exception as e:
        skipped += 1
        continue

    np.save(out, spec)
    spec_paths.append(out)
    labels.append(row['label'])

    if (i + 1) % 300 == 0:
        elapsed = time.time() - t0
        print(f'  {i+1}/{len(df)} processed  ({elapsed:.0f}s elapsed)')

print(f'Done. {len(spec_paths)} spectrograms saved, {skipped} skipped.')

# ── 3. Train / val / test split ───────────────────────────────────────────────

print('\n── Step 3: Splitting dataset ──────────────────────────────────────────')

X = np.array(spec_paths)
y = np.array(labels)

X_tmp, X_test, y_tmp, y_test = train_test_split(
    X, y, test_size=0.10, stratify=y, random_state=42)
X_train, X_val, y_train, y_val = train_test_split(
    X_tmp, y_tmp, test_size=0.111, stratify=y_tmp, random_state=42)

print(f'Train: {len(X_train)}  Val: {len(X_val)}  Test: {len(X_test)}')

# ── 4. tf.data pipeline ───────────────────────────────────────────────────────

def load_spec(path, label):
    # In TF 2.20 + Python 3.13, tf.numpy_function passes bytes directly (not EagerTensor)
    spec = tf.numpy_function(lambda p: np.load(p.decode()), [path], tf.float32)
    spec.set_shape([IMG_SIZE, IMG_SIZE])
    spec = tf.stack([spec, spec, spec], axis=-1)   # (128,128,3)
    return spec, tf.cast(label, tf.int32)


def make_ds(paths, lbls, training=False):
    ds = tf.data.Dataset.from_tensor_slices((paths, lbls))
    ds = ds.map(load_spec, num_parallel_calls=tf.data.AUTOTUNE)
    if training:
        ds = ds.shuffle(1000, seed=42)
    return ds.batch(BATCH_SIZE).prefetch(tf.data.AUTOTUNE)


train_ds = make_ds(X_train, y_train, training=True)
val_ds   = make_ds(X_val,   y_val)
test_ds  = make_ds(X_test,  y_test)

# ── 5. Build model ────────────────────────────────────────────────────────────

print('\n── Step 4: Building MobileNetV2 model ─────────────────────────────────')

def build_model(trainable_backbone=False):
    inputs = keras.Input(shape=(IMG_SIZE, IMG_SIZE, 3))

    # MobileNetV2 expects [0, 255] but we'll rescale from [0,1]
    x = layers.Rescaling(scale=255.0)(inputs)
    x = keras.applications.mobilenet_v2.preprocess_input(x)   # → [-1, 1]

    backbone = keras.applications.MobileNetV2(
        include_top=False, weights='imagenet',
        input_shape=(IMG_SIZE, IMG_SIZE, 3)
    )
    backbone.trainable = trainable_backbone

    x = backbone(x, training=False)
    x = layers.GlobalAveragePooling2D()(x)
    x = layers.BatchNormalization()(x)
    x = layers.Dropout(0.3)(x)
    x = layers.Dense(256, activation='relu')(x)
    x = layers.Dropout(0.2)(x)
    outputs = layers.Dense(N_CLASSES, activation='softmax')(x)

    return keras.Model(inputs, outputs)


model = build_model(trainable_backbone=False)
total  = sum(np.prod(v.shape) for v in model.variables)
trainable = sum(np.prod(v.shape) for v in model.trainable_variables)
print(f'Total params    : {total:,}')
print(f'Trainable params: {trainable:,}  (backbone frozen)')

# ── 6. Phase 1 — Train head ───────────────────────────────────────────────────

print(f'\n── Step 5: Phase 1 — Head training ({EPOCHS_HEAD} epochs, backbone frozen) ──')
print('  Expected time: 1–2 hours on CPU\n')

model.compile(
    optimizer=keras.optimizers.Adam(LR_HEAD),
    loss='sparse_categorical_crossentropy',
    metrics=['accuracy']
)

cb_ckpt1 = callbacks.ModelCheckpoint(
    os.path.join(MODEL_DIR, 'best_head.keras'),
    monitor='val_accuracy', save_best_only=True, verbose=1
)
cb_lr = callbacks.ReduceLROnPlateau(
    monitor='val_loss', factor=0.5, patience=2, verbose=1, min_lr=1e-6
)

t_phase1 = time.time()
hist1 = model.fit(train_ds, validation_data=val_ds,
                  epochs=EPOCHS_HEAD, callbacks=[cb_ckpt1, cb_lr])
print(f'Phase 1 done in {(time.time()-t_phase1)/60:.1f} min')

# ── 7. Phase 2 — Fine-tune ────────────────────────────────────────────────────

print(f'\n── Step 6: Phase 2 — Fine-tuning ({EPOCHS_FINE} epochs, top 30 layers) ───')
print('  Expected time: 4–8 hours on CPU\n')

model.load_weights(os.path.join(MODEL_DIR, 'best_head.keras'))

backbone = None
for layer in model.layers:
    if isinstance(layer, keras.Model):
        backbone = layer
        break

if backbone:
    backbone.trainable = True
    for layer in backbone.layers[:-30]:
        layer.trainable = False
    trainable = sum(np.prod(v.shape) for v in model.trainable_variables)
    print(f'Trainable params after unfreeze: {trainable:,}')

model.compile(
    optimizer=keras.optimizers.Adam(LR_FINE),
    loss='sparse_categorical_crossentropy',
    metrics=['accuracy']
)

cb_ckpt2 = callbacks.ModelCheckpoint(
    os.path.join(MODEL_DIR, 'best_finetune.keras'),
    monitor='val_accuracy', save_best_only=True, verbose=1
)
cb_early = callbacks.EarlyStopping(
    monitor='val_accuracy', patience=5, restore_best_weights=True, verbose=1
)

t_phase2 = time.time()
hist2 = model.fit(train_ds, validation_data=val_ds,
                  epochs=EPOCHS_FINE, callbacks=[cb_ckpt2, cb_early])
print(f'Phase 2 done in {(time.time()-t_phase2)/60:.1f} min')

# ── 8. Evaluation ─────────────────────────────────────────────────────────────

print('\n── Step 7: Evaluation ─────────────────────────────────────────────────')

model.load_weights(os.path.join(MODEL_DIR, 'best_finetune.keras'))

y_pred = np.argmax(model.predict(test_ds, verbose=0), axis=1)
f1 = f1_score(y_test, y_pred, average='macro')

print(f'\nTest macro-F1 : {f1:.4f}  (previous deployed model: 0.884)')
print()
print(classification_report(y_test, y_pred, target_names=CLASSES))

# Save training curves
fig, axes = plt.subplots(1, 2, figsize=(12, 4))
for ax, hist, title in zip(axes, [hist1, hist2], ['Phase 1 (head)', 'Phase 2 (fine-tune)']):
    ax.plot(hist.history['accuracy'], label='train')
    ax.plot(hist.history['val_accuracy'], label='val')
    ax.set_title(title); ax.legend(); ax.set_xlabel('epoch'); ax.set_ylabel('accuracy')
plt.tight_layout()
curves_path = os.path.join(MODEL_DIR, 'training_curves.png')
plt.savefig(curves_path, dpi=120)
print(f'Training curves saved to {curves_path}')

# ── 9. Export to TFLite INT8 ──────────────────────────────────────────────────

print('\n── Step 8: Exporting to TFLite INT8 ──────────────────────────────────')

saved_path = os.path.join(MODEL_DIR, 'snore_classifier_savedmodel')
model.export(saved_path)   # Keras 3 API: export() produces SavedModel for TFLite
print(f'SavedModel exported to {saved_path}')

# Build a representative dataset for INT8 calibration
def representative_dataset():
    for path_batch, _ in val_ds.take(20):
        for spec in path_batch:
            yield [tf.expand_dims(spec, 0)]

converter = tf.lite.TFLiteConverter.from_saved_model(saved_path)
converter.optimizations = [tf.lite.Optimize.DEFAULT]
converter.representative_dataset = representative_dataset
converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
converter.inference_input_type  = tf.float32   # keep float IO for mobile ease
converter.inference_output_type = tf.float32

tflite_model = converter.convert()

with open(TFLITE_OUT, 'wb') as f:
    f.write(tflite_model)

size_mb = os.path.getsize(TFLITE_OUT) / 1024 / 1024
print(f'\nTFLite model saved to {TFLITE_OUT}')
print(f'Model size: {size_mb:.2f} MB')
print(f'Test F1   : {f1:.4f}')

# Save class map alongside model
class_map_path = os.path.join(MODEL_DIR, 'class_map.json')
with open(class_map_path, 'w') as f:
    json.dump({str(i): c for i, c in enumerate(CLASSES)}, f, indent=2)
print(f'Class map  : {class_map_path}')

print('\n✅ Done! Rebuild the APK to ship the updated model.')
if f1 >= 0.884:
    print(f'   Model improved over deployed baseline (0.884 → {f1:.3f})')
else:
    print(f'   ⚠️  F1 {f1:.3f} below baseline 0.884 — try adding more snoring data or running more epochs.')
