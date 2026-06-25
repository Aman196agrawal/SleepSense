/**
 * Minimal PCM16 → WAV encoding, pure + dependency-light so it can be unit-tested
 * off-device. Used by RecordScreen to assemble a discrete 30-second WAV file from
 * the continuous PCM stream (no recorder stop/restart) for chunk upload.
 */

/** Concatenate a list of byte arrays into one Uint8Array. */
export function concatBytes(parts: Uint8Array[]): Uint8Array {
  let total = 0;
  for (const p of parts) total += p.length;
  const out = new Uint8Array(total);
  let off = 0;
  for (const p of parts) { out.set(p, off); off += p.length; }
  return out;
}

/** Standard base64 encode of raw bytes (no atob/Buffer dependency). */
const _B64 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
export function bytesToBase64(bytes: Uint8Array): string {
  let out = '';
  let i = 0;
  const n = bytes.length;
  for (; i + 2 < n; i += 3) {
    const x = (bytes[i] << 16) | (bytes[i + 1] << 8) | bytes[i + 2];
    out += _B64[(x >> 18) & 63] + _B64[(x >> 12) & 63] + _B64[(x >> 6) & 63] + _B64[x & 63];
  }
  const rem = n - i;
  if (rem === 1) {
    const x = bytes[i] << 16;
    out += _B64[(x >> 18) & 63] + _B64[(x >> 12) & 63] + '==';
  } else if (rem === 2) {
    const x = (bytes[i] << 16) | (bytes[i + 1] << 8);
    out += _B64[(x >> 18) & 63] + _B64[(x >> 12) & 63] + _B64[(x >> 6) & 63] + '=';
  }
  return out;
}

const _writeAscii = (view: DataView, offset: number, s: string) => {
  for (let i = 0; i < s.length; i++) view.setUint8(offset + i, s.charCodeAt(i));
};

/** Build a 44-byte canonical PCM WAV header for `dataLen` bytes of audio. */
export function wavHeader(dataLen: number, sampleRate: number, channels: number, bitDepth: number): Uint8Array {
  const buf = new ArrayBuffer(44);
  const v = new DataView(buf);
  const byteRate = (sampleRate * channels * bitDepth) >> 3;
  const blockAlign = (channels * bitDepth) >> 3;
  _writeAscii(v, 0, 'RIFF');
  v.setUint32(4, 36 + dataLen, true);   // RIFF chunk size
  _writeAscii(v, 8, 'WAVE');
  _writeAscii(v, 12, 'fmt ');
  v.setUint32(16, 16, true);            // fmt chunk size (PCM)
  v.setUint16(20, 1, true);             // audio format = PCM
  v.setUint16(22, channels, true);
  v.setUint32(24, sampleRate, true);
  v.setUint32(28, byteRate, true);
  v.setUint16(32, blockAlign, true);
  v.setUint16(34, bitDepth, true);
  _writeAscii(v, 36, 'data');
  v.setUint32(40, dataLen, true);       // data chunk size
  return new Uint8Array(buf);
}

/**
 * Wrap raw little-endian PCM byte chunks in a WAV container and return it as a
 * base64 string (ready for FileSystem.writeAsStringAsync with Base64 encoding).
 */
export function encodeWavBase64(
  pcmChunks: Uint8Array[],
  sampleRate: number,
  channels = 1,
  bitDepth = 16,
): string {
  const data = concatBytes(pcmChunks);
  const wav = concatBytes([wavHeader(data.length, sampleRate, channels, bitDepth), data]);
  return bytesToBase64(wav);
}
