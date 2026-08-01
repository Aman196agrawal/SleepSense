/**
 * Live original-vs-cleaned audio view.
 *
 *   @siteed/expo-audio-studio ──base64 PCM──┬─────────────────────► ORIGINAL waveform
 *                                           └─ SnoreBandFilter ───► CLEANED waveform
 *
 * Both traces are built from the same PCM block, so any difference on screen is
 * the filter and never a timing skew between the panels.
 *
 * A mel spectrogram used to sit below these two. It was removed once the
 * waveforms were judged sufficient on their own; RecordScreen still renders one,
 * so LiveSpectrogram and the mel DSP in ml/spectrogram remain in use.
 */
import React, { useCallback, useRef, useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, Dimensions } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAudioRecorder, type AudioDataEvent } from '@siteed/expo-audio-studio';
import { Asset } from 'expo-asset';
import * as FileSystem from 'expo-file-system/legacy';

import { LiveWaveform, type LiveWaveformHandle } from '../components/LiveWaveform';
import { SnoreBandFilter } from '../ml/biquad';
import {
  pcm16Base64ToFloat32, base64ToBytes, pcm16BytesToFloat32, SR,
} from '../ml/spectrogram';
import { parseWavPcm16 } from '../ml/wav';

const { width: SCREEN_W } = Dimensions.get('window');
const SPEC_W = Math.round(SCREEN_W - 32);

const WAVE_H = 150;

export default function LiveAudioScreen() {
  const { startRecording, stopRecording, isRecording } = useAudioRecorder();
  const rawWaveRef = useRef<LiveWaveformHandle>(null);
  const cleanWaveRef = useRef<LiveWaveformHandle>(null);
  // Time-domain cleaner for the second trace. Holds filter state across blocks,
  // so it is rebuilt whenever the sample rate changes.
  const filterRef = useRef(new SnoreBandFilter(SR));
  const [err, setErr] = useState<string | null>(null);
  const [rate, setRate] = useState<number>(SR);
  const [playing, setPlaying] = useState(false);
  const cancelRef = useRef(false);

  const onAudioStream = useCallback(async (event: AudioDataEvent) => {
    try {
      // On native, `data` is a base64 PCM16 string; on web it's already a typed array.
      const pcm = typeof event.data === 'string'
        ? pcm16Base64ToFloat32(event.data)
        : Float32Array.from(event.data as Float32Array);
      // Both traces come from the same PCM block, so any visible difference is
      // the filter and never a timing skew between the two panels.
      rawWaveRef.current?.push(pcm);
      cleanWaveRef.current?.push(filterRef.current.process(pcm));

    } catch (e: any) {
      setErr(String(e?.message ?? e));
    }
  }, []);

  const start = useCallback(async () => {
    setErr(null);
    filterRef.current.reset();
    rawWaveRef.current?.clear();
    cleanWaveRef.current?.clear();
    try {
      const res = await startRecording({
        sampleRate: SR,
        channels: 1,
        encoding: 'pcm_16bit',
        interval: 100,                 // emit PCM ~10×/sec
        keepAwake: true,
        onAudioStream,
        // streaming-only for the test (no file needed yet)
        output: { primary: { enabled: false } },
      });
      // Android often ignores the requested rate. Rebuild the filterbank for
      // whatever we actually got, or every tone lands in the wrong mel bin.
      const actual = res?.sampleRate ?? SR;
      setRate(actual);
      if (actual !== filterRef.current.sampleRate) {
        filterRef.current = new SnoreBandFilter(actual);
      }
    } catch (e: any) {
      setErr(String(e?.message ?? e));
    }
  }, [startRecording, onAudioStream]);

  const stop = useCallback(async () => {
    try { await stopRecording(); } catch (e: any) { setErr(String(e?.message ?? e)); }
  }, [stopRecording]);

  /**
   * Replay a bundled snore clip through the SAME streamer the mic feeds, in
   * 100ms blocks paced in real time — identical to what onAudioStream delivers.
   * Lets the visualisation be demoed without a microphone (the emulator's
   * virtual mic records silence) and gives a repeatable result.
   */
  const playSample = useCallback(async () => {
    if (isRecording || playing) return;
    setErr(null);
    setPlaying(true);
    cancelRef.current = false;
    try {
      const asset = Asset.fromModule(require('../../assets/audio/snore-sample.wav'));
      await asset.downloadAsync();
      const uri = asset.localUri ?? asset.uri;
      const b64 = await FileSystem.readAsStringAsync(uri, { encoding: 'base64' });
      const { data, sampleRate } = parseWavPcm16(base64ToBytes(b64));
      const pcm = pcm16BytesToFloat32(data);

      setRate(sampleRate);
      filterRef.current = new SnoreBandFilter(sampleRate);
      rawWaveRef.current?.clear();
      cleanWaveRef.current?.clear();

      const block = Math.max(1, Math.round(sampleRate / 10));   // 100ms
      for (let i = 0; i < pcm.length && !cancelRef.current; i += block) {
        const slice = pcm.subarray(i, Math.min(i + block, pcm.length));
        rawWaveRef.current?.push(slice);
        cleanWaveRef.current?.push(filterRef.current.process(slice));
        await new Promise(r => setTimeout(r, 100));
      }
    } catch (e: any) {
      setErr(String(e?.message ?? e));
    } finally {
      setPlaying(false);
    }
  }, [isRecording, playing]);

  return (
    <SafeAreaView style={styles.root}>
      <Text style={styles.title}>Live Audio</Text>
      <Text style={styles.sub}>
        Original against cleaned, in real time. Tap Start and snore, or replay the bundled sample.
      </Text>
      <Text style={styles.meta}>
        {isRecording ? `recording @ ${rate} Hz` : 'idle'}
        {rate !== SR ? `  (device overrode ${SR} Hz)` : ''}
      </Text>

      <LiveWaveform
        ref={rawWaveRef}
        width={SPEC_W}
        height={WAVE_H}
        sampleRate={rate}
        label="ORIGINAL"
        color="#4C9BE8"
      />
      <LiveWaveform
        ref={cleanWaveRef}
        width={SPEC_W}
        height={WAVE_H}
        sampleRate={rate}
        label={`CLEANED  ${filterRef.current.lowHz}-${filterRef.current.highHz} Hz`}
        color="#34D399"
      />


      <TouchableOpacity
        style={[styles.btn, isRecording ? styles.stop : styles.start,
                playing && styles.disabled]}
        onPress={isRecording ? stop : start}
        disabled={playing}
      >
        <Text style={styles.btnText}>{isRecording ? 'Stop' : 'Start'}</Text>
      </TouchableOpacity>

      <TouchableOpacity
        style={[styles.btn, styles.sample, (isRecording || playing) && styles.disabled]}
        onPress={playing ? () => { cancelRef.current = true; } : playSample}
        disabled={isRecording}
      >
        <Text style={styles.btnText}>
          {playing ? 'Stop sample' : 'Play sample'}
        </Text>
      </TouchableOpacity>

      {err && <Text style={styles.err}>{err}</Text>}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#0B0B14', alignItems: 'center', paddingTop: 24, gap: 16 },
  title: { color: '#fff', fontSize: 18, fontWeight: '700' },
  sub: { color: '#9aa', fontSize: 13, paddingHorizontal: 24, textAlign: 'center' },
  meta: { color: '#667', fontSize: 11, textAlign: 'center' },
  btn: { paddingVertical: 14, paddingHorizontal: 48, borderRadius: 28, marginTop: 12 },
  start: { backgroundColor: '#A78BFA' },
  stop: { backgroundColor: '#EF4444' },
  sample: { backgroundColor: '#2F3350' },
  disabled: { opacity: 0.4 },
  btnText: { color: '#fff', fontSize: 16, fontWeight: '700' },
  err: { color: '#EF4444', fontSize: 12, paddingHorizontal: 24, textAlign: 'center' },
});
