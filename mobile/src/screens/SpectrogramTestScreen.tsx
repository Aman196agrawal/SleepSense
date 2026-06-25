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

import { LiveSpectrogram, type LiveSpectrogramHandle } from '../components/LiveSpectrogram';
import { MelSpectrogramStreamer, pcm16Base64ToFloat32, MEL_DISPLAY, SR } from '../ml/spectrogram';

const { width: SCREEN_W } = Dimensions.get('window');
const SPEC_W = Math.round(SCREEN_W - 32);
const SPEC_H = 220;

export default function SpectrogramTestScreen() {
  const { startRecording, stopRecording, isRecording } = useAudioRecorder();
  const streamerRef = useRef(new MelSpectrogramStreamer(MEL_DISPLAY));
  const specRef = useRef<LiveSpectrogramHandle>(null);
  const [err, setErr] = useState<string | null>(null);

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
      await startRecording({
        sampleRate: SR,
        channels: 1,
        encoding: 'pcm_16bit',
        interval: 100,                 // emit PCM ~10×/sec
        keepAwake: true,
        onAudioStream,
        // streaming-only for the test (no file needed yet)
        output: { primary: { enabled: false } },
      });
    } catch (e: any) {
      setErr(String(e?.message ?? e));
    }
  }, [startRecording, onAudioStream]);

  const stop = useCallback(async () => {
    try { await stopRecording(); } catch (e: any) { setErr(String(e?.message ?? e)); }
  }, [stopRecording]);

  return (
    <SafeAreaView style={styles.root}>
      <Text style={styles.title}>Live Spectrogram — pipeline test</Text>
      <Text style={styles.sub}>
        Tap Start and hum/snore. Energy should light up the low-mid bands.
      </Text>

      <LiveSpectrogram
        ref={specRef}
        nMels={MEL_DISPLAY}
        width={SPEC_W}
        height={SPEC_H}
        style={styles.spec}
      />

      <TouchableOpacity
        style={[styles.btn, isRecording ? styles.stop : styles.start]}
        onPress={isRecording ? stop : start}
      >
        <Text style={styles.btnText}>{isRecording ? 'Stop' : 'Start'}</Text>
      </TouchableOpacity>

      {err && <Text style={styles.err}>{err}</Text>}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#0B0B14', alignItems: 'center', paddingTop: 24, gap: 16 },
  title: { color: '#fff', fontSize: 18, fontWeight: '700' },
  sub: { color: '#9aa', fontSize: 13, paddingHorizontal: 24, textAlign: 'center' },
  spec: { marginTop: 8 },
  btn: { paddingVertical: 14, paddingHorizontal: 48, borderRadius: 28, marginTop: 12 },
  start: { backgroundColor: '#A78BFA' },
  stop: { backgroundColor: '#EF4444' },
  btnText: { color: '#fff', fontSize: 16, fontWeight: '700' },
  err: { color: '#EF4444', fontSize: 12, paddingHorizontal: 24, textAlign: 'center' },
});
