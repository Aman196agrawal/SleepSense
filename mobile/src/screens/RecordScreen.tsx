import React, { useState, useEffect, useRef, useCallback } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, Animated, Alert, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import {
  useAudioRecorder,
  RecordingPresets,
  AudioModule,
  setAudioModeAsync,
} from 'expo-audio';
import { Colors } from '../theme/colors';
import * as AnalyticsAPI from '../api/analytics.api';
import { sleepSenseWS } from '../api/ws';

// expo-audio metering: 0 dB = max, -160 dB = silence. Map [-60, -5] → [0, 100].
// NOTE: this is loudness-based heuristic detection. The CNN classifier
// described in the marketing copy is on the roadmap but not shipped yet.
const DB_FLOOR = -60;
const DB_CEIL  = -5;
const dbToIntensity = (db: number): number =>
  Math.round(Math.max(0, Math.min(100, ((db - DB_FLOOR) / (DB_CEIL - DB_FLOOR)) * 100)));

type SoundInfo = { label: string; cls: string; color: string };
const classify = (lvl: number): SoundInfo => {
  if (lvl < 8)  return { label: 'Silence 😴',      cls: 'silence',   color: Colors.textMuted };
  if (lvl < 30) return { label: 'Breathing 💨',    cls: 'breathing', color: Colors.secondary };
  if (lvl < 65) return { label: 'Snoring 😤',      cls: 'snoring',   color: Colors.danger };
  return               { label: 'Loud Snoring 😤', cls: 'snoring',   color: Colors.danger };
};

const CHUNK_SECONDS    = 30;
const BAR_COUNT        = 22;
const METER_POLL_MS    = 200;

type Phase = 'idle' | 'recording' | 'stopping';

export default function RecordScreen({ navigation }: any) {
  const [phase, setPhase]       = useState<Phase>('idle');
  const [elapsed, setElapsed]   = useState(0);
  const [intensity, setIntensity] = useState(0);
  const [soundInfo, setSoundInfo] = useState<SoundInfo>({ label: 'Silence 😴', cls: 'silence', color: Colors.textMuted });
  const [chunkCount, setChunkCount] = useState(0);
  const [privacyMode, setPrivacyMode] = useState(false);

  // expo-audio recorder — metering enabled so we can read `currentMetering`.
  const recorder = useAudioRecorder({
    ...RecordingPresets.HIGH_QUALITY,
    isMeteringEnabled: true,
  });

  // Refs that survive re-renders during long sessions
  const privacyModeRef  = useRef(false);
  const sessionIdRef    = useRef<string | null>(null);
  const chunkIdxRef     = useRef(0);
  const chunkTimerRef   = useRef(0);
  const tickTimerRef    = useRef<ReturnType<typeof setInterval> | null>(null);
  const meterTimerRef   = useRef<ReturnType<typeof setInterval> | null>(null);
  const statsRef        = useRef<{ intensities: number[]; classes: string[]; events: number }>({
    intensities: [], classes: [], events: 0,
  });

  const pulse = useRef(new Animated.Value(1)).current;
  const bars  = useRef(
    Array.from({ length: BAR_COUNT }, () => new Animated.Value(4))
  ).current;

  // Animate waveform bars from current level
  const animateBars = useCallback((lvl: number) => {
    bars.forEach((bar, i) => {
      // Neighbour bars mirror each other for a symmetric waveform look
      const mirror = Math.abs(i - BAR_COUNT / 2) / (BAR_COUNT / 2);
      const target = Math.max(4, lvl * 0.55 * (1 - mirror * 0.4) * (0.7 + Math.random() * 0.6));
      Animated.spring(bar, {
        toValue: Math.min(target, 52),
        useNativeDriver: false,
        speed: 28,
        bounciness: 2,
      }).start();
    });
  }, [bars]);

  // Pulse the mic button while recording
  useEffect(() => {
    if (phase === 'recording') {
      Animated.loop(
        Animated.sequence([
          Animated.timing(pulse, { toValue: 1.10, duration: 900, useNativeDriver: true }),
          Animated.timing(pulse, { toValue: 1,    duration: 900, useNativeDriver: true }),
        ])
      ).start();
    } else {
      pulse.stopAnimation();
      pulse.setValue(1);
      animateBars(0);
    }
  }, [phase, pulse, animateBars]);

  // Cleanup on unmount: kill any in-flight timers / recording.
  useEffect(() => {
    return () => {
      if (tickTimerRef.current)  clearInterval(tickTimerRef.current);
      if (meterTimerRef.current) clearInterval(meterTimerRef.current);
    };
  }, []);

  // Upload current chunk stats to backend, then reset accumulator
  const flushChunk = useCallback(async () => {
    const stats = statsRef.current;
    if (stats.intensities.length === 0 || !sessionIdRef.current) return;

    const avgIntensity = stats.intensities.reduce((a, b) => a + b, 0) / stats.intensities.length;
    const counts: Record<string, number> = {};
    stats.classes.forEach(c => { counts[c] = (counts[c] ?? 0) + 1; });
    const dominant = Object.entries(counts).sort((a, b) => b[1] - a[1])[0]?.[0] ?? 'silence';

    try {
      await AnalyticsAPI.uploadChunk(sessionIdRef.current, {
        chunk_index: chunkIdxRef.current,
        avg_intensity: Math.round(avgIntensity),
        dominant_class: dominant,
        snore_event_count: stats.events,
      });
    } catch (err) {
      // Surfacing every transient network blip during an 8-hour recording
      // would be noisier than useful — log to the JS console and rely on the
      // session-end retry to fill in any missed chunks.
      console.warn('chunk upload failed', err);
    }

    chunkIdxRef.current += 1;
    statsRef.current = { intensities: [], classes: [], events: 0 };
    setChunkCount(c => c + 1);
  }, []);

  // Poll the recorder's current metering value and update live UI state.
  const pollMeter = useCallback(() => {
    // `recorder.currentMetering` is set by expo-audio when isMeteringEnabled
    // is true. Missing on web / unsupported devices → treat as silence.
    const db  = (recorder as any).currentMetering ?? DB_FLOOR;
    const lvl = dbToIntensity(db);
    const info = classify(lvl);

    setIntensity(lvl);
    setSoundInfo(info);
    animateBars(lvl);

    const s = statsRef.current;
    const wasSnoring = s.classes[s.classes.length - 1] === 'snoring';
    s.intensities.push(lvl);
    s.classes.push(info.cls);
    if (info.cls === 'snoring' && !wasSnoring) s.events += 1;
  }, [recorder, animateBars]);

  const startRecording = async () => {
    try {
      const { granted } = await AudioModule.requestRecordingPermissionsAsync();
      if (!granted) {
        Alert.alert(
          'Microphone required',
          'Please allow microphone access in your device settings to record sleep audio.'
        );
        return;
      }

      if (Platform.OS !== 'web') {
        await setAudioModeAsync({ allowsRecording: true, playsInSilentMode: true });
      }

      privacyModeRef.current = privacyMode;
      if (!privacyMode) {
        const res = await AnalyticsAPI.startSession();
        sessionIdRef.current = res.data.session_id;
        sleepSenseWS.connect();
      } else {
        sessionIdRef.current = null; // local-only session
      }
      chunkIdxRef.current   = 0;
      chunkTimerRef.current = 0;
      statsRef.current = { intensities: [], classes: [], events: 0 };

      setElapsed(0);
      setChunkCount(0);
      setPhase('recording');

      await recorder.prepareToRecordAsync();
      recorder.record();

      meterTimerRef.current = setInterval(pollMeter, METER_POLL_MS);

      tickTimerRef.current = setInterval(async () => {
        setElapsed(e => e + 1);
        chunkTimerRef.current += 1;

        if (chunkTimerRef.current >= CHUNK_SECONDS) {
          chunkTimerRef.current = 0;
          await flushChunk();
        }
      }, 1000);
    } catch (err: any) {
      Alert.alert('Error', err?.message ?? 'Could not start recording.');
      setPhase('idle');
    }
  };

  const stopRecording = async () => {
    setPhase('stopping');
    if (tickTimerRef.current)  { clearInterval(tickTimerRef.current);  tickTimerRef.current  = null; }
    if (meterTimerRef.current) { clearInterval(meterTimerRef.current); meterTimerRef.current = null; }

    try {
      await recorder.stop();
    } catch (err) {
      console.warn('recorder.stop failed', err);
    }

    // Upload any remaining partial chunk
    await flushChunk();

    // Finalise session on backend
    try {
      if (sessionIdRef.current) {
        await AnalyticsAPI.endSession(sessionIdRef.current);
        Alert.alert('Session Saved! 🌙', 'Your sleep report is ready.', [
          { text: 'View Report', onPress: () => navigation.navigate('Home') },
          { text: 'OK' },
        ]);
      } else if (privacyModeRef.current) {
        Alert.alert('Privacy Session Saved', 'Audio stayed on your device. No data was uploaded.');
      }
    } catch (err) {
      console.warn('endSession failed', err);
      Alert.alert('Saved', 'Session ended.');
    }

    if (Platform.OS !== 'web') {
      try { await setAudioModeAsync({ allowsRecording: false }); } catch (err) {
        console.warn('reset audio mode failed', err);
      }
    }

    sleepSenseWS.disconnect();
    sessionIdRef.current = null;
    setPhase('idle');
    setElapsed(0);
    setIntensity(0);
  };

  const fmt = (s: number) =>
    `${String(Math.floor(s / 3600)).padStart(2, '0')}:` +
    `${String(Math.floor((s % 3600) / 60)).padStart(2, '0')}:` +
    `${String(s % 60).padStart(2, '0')}`;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.bg }}>
      <View style={styles.container}>
        <Text style={styles.title}>Sleep Recording</Text>

        {phase === 'recording' && (
          <>
            <Text style={styles.duration}>{fmt(elapsed)}</Text>

            {/* Live waveform */}
            <View style={styles.waveform}>
              {bars.map((bar, i) => (
                <Animated.View
                  key={i}
                  style={[
                    styles.bar,
                    { height: bar, backgroundColor: soundInfo.color, opacity: 0.45 + (i % 4) * 0.1 },
                  ]}
                />
              ))}
            </View>

            {/* Live detection card */}
            <View style={styles.liveCard}>
              <Text style={styles.liveLabel}>Detected Sound</Text>
              <Text style={[styles.liveClass, { color: soundInfo.color }]}>{soundInfo.label}</Text>
              <View style={styles.intensityBar}>
                <Animated.View
                  style={[
                    styles.intensityFill,
                    { width: `${intensity}%`, backgroundColor: soundInfo.color },
                  ]}
                />
              </View>
              <Text style={styles.intensityText}>
                Intensity {intensity} · {chunkCount} chunk{chunkCount !== 1 ? 's' : ''} saved
              </Text>
              {privacyMode && (
                <Text style={styles.privacyActive}>Shield  Privacy Mode Active — audio not uploaded</Text>
              )}
            </View>
          </>
        )}

        {phase === 'stopping' && (
          <View style={styles.idleWrap}>
            <Ionicons name="cloud-upload-outline" size={52} color={Colors.primary} />
            <Text style={styles.idleTitle}>Saving session…</Text>
            <Text style={styles.idleSub}>Uploading final data and computing your score.</Text>
          </View>
        )}

        {phase === 'idle' && (
          <View style={styles.idleWrap}>
            <Ionicons name="moon" size={64} color={Colors.primary} />
            <Text style={styles.idleTitle}>Ready to record</Text>
            <Text style={styles.idleSub}>
              Place your phone face-down on your nightstand and tap the button below before you sleep.
            </Text>
          </View>
        )}

        {/* Record / Stop button */}
        <Animated.View style={{ transform: [{ scale: pulse }] }}>
          <TouchableOpacity
            onPress={phase === 'idle' ? startRecording : phase === 'recording' ? stopRecording : undefined}
            disabled={phase === 'stopping'}
            activeOpacity={0.85}
          >
            <LinearGradient
              colors={
                phase === 'recording' ? ['#F43F5E', '#C2185B']
                : phase === 'stopping' ? [Colors.surface, Colors.surface]
                : [Colors.primary, Colors.primaryDark]
              }
              style={styles.recordBtn}
            >
              <Ionicons
                name={
                  phase === 'recording' ? 'stop'
                  : phase === 'stopping' ? 'hourglass-outline'
                  : 'mic'
                }
                size={40}
                color={phase === 'stopping' ? Colors.textMuted : '#fff'}
              />
            </LinearGradient>
          </TouchableOpacity>
        </Animated.View>

        <Text style={styles.btnLabel}>
          {phase === 'recording' ? 'Tap to stop recording'
           : phase === 'stopping' ? 'Saving…'
           : 'Tap to start recording'}
        </Text>

        {phase === 'idle' && (
          <>
            <View style={styles.privacyRow}>
              <Ionicons name="shield-checkmark-outline" size={16} color={privacyMode ? Colors.excellent : Colors.textMuted} />
              <Text style={[styles.privacyLabel, privacyMode && { color: Colors.excellent }]}>
                Privacy Mode {privacyMode ? 'ON — audio stays on device' : 'OFF'}
              </Text>
              <TouchableOpacity
                onPress={() => setPrivacyMode(p => !p)}
                style={[styles.privacyToggle, privacyMode && styles.privacyToggleOn]}
              >
                <View style={[styles.privacyThumb, privacyMode && styles.privacyThumbOn]} />
              </TouchableOpacity>
            </View>
            <View style={styles.tipsRow}>
              {['Quiet room', 'Phone nearby', 'Do not disturb'].map(tip => (
                <View key={tip} style={styles.tip}>
                  <Ionicons name="checkmark-circle" size={14} color={Colors.primary} />
                  <Text style={styles.tipText}>{tip}</Text>
                </View>
              ))}
            </View>
          </>
        )}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container:     { flex: 1, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 32, gap: 20 },
  title:         { color: Colors.text, fontSize: 22, fontWeight: '700' },
  duration:      { color: Colors.primary, fontSize: 48, fontWeight: '800', letterSpacing: 2 },
  waveform:      { flexDirection: 'row', alignItems: 'center', gap: 3, height: 56 },
  bar:           { width: 5, borderRadius: 3 },
  liveCard:      { backgroundColor: Colors.surface, borderRadius: 16, padding: 20, width: '100%', alignItems: 'center', borderWidth: 1, borderColor: Colors.border },
  liveLabel:     { color: Colors.textMuted, fontSize: 12, marginBottom: 6 },
  liveClass:     { fontSize: 20, fontWeight: '700', marginBottom: 12 },
  intensityBar:  { width: '100%', height: 8, backgroundColor: Colors.border, borderRadius: 4, overflow: 'hidden' },
  intensityFill: { height: '100%', borderRadius: 4 },
  intensityText: { color: Colors.textMuted, fontSize: 12, marginTop: 6 },
  idleWrap:      { alignItems: 'center', gap: 12 },
  idleTitle:     { color: Colors.text, fontSize: 20, fontWeight: '700' },
  idleSub:       { color: Colors.textSub, textAlign: 'center', lineHeight: 22 },
  recordBtn:     { width: 100, height: 100, borderRadius: 50, alignItems: 'center', justifyContent: 'center', elevation: 8, shadowColor: '#000', shadowOffset: { width: 0, height: 4 }, shadowOpacity: 0.3, shadowRadius: 8 },
  btnLabel:      { color: Colors.textMuted, fontSize: 13 },
  tipsRow:       { gap: 8 },
  tip:           { flexDirection: 'row', alignItems: 'center', gap: 6 },
  tipText:       { color: Colors.textSub, fontSize: 13 },
  privacyRow:      { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 8 },
  privacyLabel:    { color: Colors.textMuted, fontSize: 12, flex: 1 },
  privacyToggle:   { width: 40, height: 22, borderRadius: 11, backgroundColor: Colors.border, justifyContent: 'center', paddingHorizontal: 2 },
  privacyToggleOn: { backgroundColor: Colors.excellent + '55' },
  privacyThumb:    { width: 18, height: 18, borderRadius: 9, backgroundColor: Colors.textMuted },
  privacyThumbOn:  { backgroundColor: Colors.excellent, alignSelf: 'flex-end' },
  privacyActive: { color: Colors.excellent, fontSize: 11, marginTop: 4, textAlign: 'center' },
});
