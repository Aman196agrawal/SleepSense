/**
 * VERIFICATION SCREEN (temporary) — proves the live-spectrogram pipeline on a
 * real device WITHOUT touching the all-night RecordScreen recorder.
 *
 *   @siteed/expo-audio-studio  ──base64 PCM──►  MelSpectrogramStreamer  ──cols──►  LiveSpectrogram (Skia)
 *
 * Mount it temporarily (e.g. add a tab in MainNavigator, or render in place of a
 * screen) and tap Start. You should see a scrolling mel spectrogram that lights
 * up in the low-mid bands when you hum/snore. Once confirmed, we wire the same
 * pipeline into RecordScreen and swap the recorder for the all-night flow.
 */
import React, { useCallback, useRef, useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, Dimensions } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAudioRecorder, type AudioDataEvent } from '@siteed/expo-audio-studio';
import { Asset } from 'expo-asset';
import * as FileSystem from 'expo-file-system/legacy';

import { LiveSpectrogram, type LiveSpectrogramHandle } from '../components/LiveSpectrogram';
import {
  MelSpectrogramStreamer, pcm16Base64ToFloat32, base64ToBytes, pcm16BytesToFloat32,
  MEL_DISPLAY, SR,
} from '../ml/spectrogram';
import { parseWavPcm16 } from '../ml/wav';

const { width: SCREEN_W } = Dimensions.get('window');
const SPEC_W = Math.round(SCREEN_W - 32);
const SPEC_H = 220;

export default function SpectrogramTestScreen() {
  const { startRecording, stopRecording, isRecording } = useAudioRecorder();
  const streamerRef = useRef(new MelSpectrogramStreamer(MEL_DISPLAY, SR));
  const specRef = useRef<LiveSpectrogramHandle>(null);
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
      const cols = streamerRef.current.push(pcm);
      if (cols.length) specRef.current?.pushColumns(cols);
    } catch (e: any) {
      setErr(String(e?.message ?? e));
    }
  }, []);

  const start = useCallback(async () => {
    setErr(null);
    streamerRef.current.reset();
    specRef.current?.clear();
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
      if (actual !== streamerRef.current.sampleRate) {
        streamerRef.current = new MelSpectrogramStreamer(MEL_DISPLAY, actual);
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
      streamerRef.current = new MelSpectrogramStreamer(MEL_DISPLAY, sampleRate);
      specRef.current?.clear();

      const block = Math.max(1, Math.round(sampleRate / 10));   // 100ms
      for (let i = 0; i < pcm.length && !cancelRef.current; i += block) {
        const cols = streamerRef.current.push(pcm.subarray(i, Math.min(i + block, pcm.length)));
        if (cols.length) specRef.current?.pushColumns(cols);
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
      <Text style={styles.title}>Live Spectrogram — pipeline test</Text>
      <Text style={styles.sub}>
        Tap Start and hum/snore. Energy should light up the low-mid bands.
      </Text>
      <Text style={styles.meta}>
        {isRecording ? `recording @ ${rate} Hz` : 'idle'}
        {rate !== SR ? `  (device overrode ${SR} Hz)` : ''}
      </Text>

      <LiveSpectrogram
        ref={specRef}
        nMels={MEL_DISPLAY}
        width={SPEC_W}
        height={SPEC_H}
        style={styles.spec}
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
  spec: { marginTop: 8 },
  btn: { paddingVertical: 14, paddingHorizontal: 48, borderRadius: 28, marginTop: 12 },
  start: { backgroundColor: '#A78BFA' },
  stop: { backgroundColor: '#EF4444' },
  sample: { backgroundColor: '#2F3350' },
  disabled: { opacity: 0.4 },
  btnText: { color: '#fff', fontSize: 16, fontWeight: '700' },
  err: { color: '#EF4444', fontSize: 12, paddingHorizontal: 24, textAlign: 'center' },
});
