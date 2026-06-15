"""
Export the trained .keras model to INT8 TFLite.
Run after train_cpu.py completes successfully.
"""
import os, sys, json
import numpy as np
import tensorflow as tf

sys.stdout.reconfigure(encoding='utf-8')

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT   = os.path.dirname(SCRIPT_DIR)
MODEL_DIR   = os.path.join(SCRIPT_DIR, 'models')
SPEC_DIR    = os.path.join(os.environ.get('TEMP', os.path.expanduser('~')), 'sleepsense_specs')
KERAS_PATH  = os.path.join(MODEL_DIR, 'best_finetune.keras')
SAVED_PATH  = os.path.join(MODEL_DIR, 'snore_classifier_savedmodel')
TFLITE_OUT  = os.path.join(REPO_ROOT, 'mobile', 'assets', 'models', 'snore_classifier.tflite')
IMG_SIZE    = 128

print(f'TensorFlow {tf.__version__}')
print(f'Loading {KERAS_PATH}')

model = tf.keras.models.load_model(KERAS_PATH)
print('Model loaded.')

# Export to SavedModel format (Keras 3 API)
print(f'Exporting SavedModel to {SAVED_PATH} ...')
model.export(SAVED_PATH)
print('SavedModel exported.')

# Build representative dataset from cached spectrograms for INT8 calibration
spec_files = sorted([
    os.path.join(SPEC_DIR, f) for f in os.listdir(SPEC_DIR)
    if f.endswith('.npy')
])[:200]

def representative_dataset():
    for path in spec_files:
        spec = np.load(path).astype(np.float32)          # (128, 128)
        spec = np.stack([spec, spec, spec], axis=-1)      # (128, 128, 3)
        yield [spec[np.newaxis, ...]]                     # (1, 128, 128, 3)

print('Converting to INT8 TFLite ...')
converter = tf.lite.TFLiteConverter.from_saved_model(SAVED_PATH)
converter.optimizations = [tf.lite.Optimize.DEFAULT]
converter.representative_dataset = representative_dataset
converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
converter.inference_input_type  = tf.float32
converter.inference_output_type = tf.float32

tflite_model = converter.convert()

with open(TFLITE_OUT, 'wb') as f:
    f.write(tflite_model)

size_mb = os.path.getsize(TFLITE_OUT) / 1024 / 1024
print(f'\nTFLite model  : {TFLITE_OUT}')
print(f'Size          : {size_mb:.2f} MB')

# Save class map
class_map = {"0": "snoring", "1": "breathing", "2": "silence", "3": "ambient"}
with open(os.path.join(MODEL_DIR, 'class_map.json'), 'w') as f:
    json.dump(class_map, f, indent=2)

print('\nDone. Rebuild the APK to ship the updated model.')
