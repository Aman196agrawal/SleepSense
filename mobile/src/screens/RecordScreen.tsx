import React, { useState, useEffect, useRef, useCallback } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, Animated, Alert, Platform, AppState, AppStateStatus, Vibration } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import {
  useAudioRecorder,
  RecordingPresets,
  AudioModule,
  setAudioModeAsync,
} from 'expo-audio';
import { Colors, Radii, Spacing, Elevation, Gradients } from '../theme';
import AuroraBackground from '../components/AuroraBackground';
import GlassCard from '../components/GlassCard';
import * as AnalyticsAPI from '../api/analytics.api';
import * as IngestionAPI from '../api/ingestion.api';
import { sleepSenseWS } from '../api/ws';
import {
  startForegroundAudioNotification,
  stopForegroundAudioNotification,
} from '../utils/foregroundService';
import { onDeviceClassifier } from '../ml/OnDeviceClassifier';

// expo-audio metering: 0 dB = max, -160 dB = silence. Map [-60, -5] → [0, 100].
// NOTE: this is loudness-based heuristic detection. The CNN classifier
// described in the marketing copy is on the roadmap but not shipped yet.
const DB_FLOOR = -60;
const DB_CEIL  = -5;
const dbToIntensity = (db: number): number =>
  Math.round(Math.max(0, Math.min(100, ((db - DB_FLOOR) / (DB_CEIL - DB_FLOOR)) * 100)));

type SoundInfo = { label: string; cls: string; color: string; icon: keyof typeof Ionicons.glyphMap };
const classify = (lvl: number): SoundInfo => {
  if (lvl < 8)  return { label: 'Silence',      cls: 'silence',   color: Colors.textMuted, icon: 'moon-outline' };
  if (lvl < 30) return { label: 'Breathing',    cls: 'breathing', color: Colors.secondary, icon: 'pulse-outline' };
  if (lvl < 65) return { label: 'Snoring',      cls: 'snoring',   color: Colors.accent,    icon: 'volume-high' };
  return               { label: 'Loud Snoring', cls: 'snoring',   color: Colors.danger,    icon: 'volume-high' };
};

const CHUNK_SECONDS    = 30;
const BAR_COUNT        = 22;
const METER_POLL_MS    = 200;

type Phase = 'idle' | 'recording' | 'stopping';

export default function RecordScreen({ navigation }: any) {
  const [phase, setPhase]       = useState<Phase>('idle');
  const [elapsed, setElapsed]   = useState(0);
  const [intensity, setIntensity] = useState(0);
  const [soundInfo, setSoundInfo] = useState<SoundInfo>({ label: 'Silence', cls: 'silence', color: Colors.textMuted, icon: 'moon-outline' });
  const [chunkCount, setChunkCount] = useState(0);
  const [privacyMode, setPrivacyMode] = useState(false);

  // expo-audio recorder — metering enabled so we can read `currentMetering`.
  const recorder = useAudioRecorder({
    ...RecordingPresets.HIGH_QUALITY,
    isMeteringEnabled: true,
  });

  // Refs that survive re-renders during long sessions
  const privacyModeRef   = useRef(false);
  const sessionIdRef     = useRef<string | null>(null);
  const chunkIdxRef      = useRef(0);
  const chunkTimerRef    = useRef(0);
  const tickTimerRef     = useRef<ReturnType<typeof setInterval> | null>(null);
  const meterTimerRef    = useRef<ReturnType<typeof setInterval> | null>(null);
  const stoppingRef      = useRef(false);   // true while stopRecording is executing
  const chunkBusyRef     = useRef(false);   // true while recorder is being cycled for a chunk
  const appStateRef      = useRef<AppStateStatus>(AppState.currentState);
  // Rolling window of dBFS readings fed to the on-device TFLite classifier
  const meteringHistRef  = useRef<number[]>([]);
  const statsRef         = useRef<{ intensities: number[]; classes: string[]; events: number }>({
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
    const sub = AppState.addEventListener('change', (next: AppStateStatus) => {
      appStateRef.current = next;
    });
    return () => {
      sub.remove();
      if (tickTimerRef.current)  clearInterval(tickTimerRef.current);
      if (meterTimerRef.current) clearInterval(meterTimerRef.current);
    };
  }, []);

  // Pre-load the TFLite model as soon as Privacy Mode is enabled so it is
  // ready before the user starts recording.
  useEffect(() => {
    if (privacyMode && !onDeviceClassifier.ready) {
      onDeviceClassifier.load();
    }
  }, [privacyMode]);

  // Upload current chunk: JSON stats to analytics-service + binary audio to ingestion-service.
  // Binary upload stops and restarts the recorder to capture a discrete 30s file.
  const flushChunk = useCallback(async () => {
    if (chunkBusyRef.current) return; // previous chunk still uploading — skip this tick
    const sid  = sessionIdRef.current;
    const idx  = chunkIdxRef.current;
    const stats = statsRef.current;
    if (!sid || privacyModeRef.current) {
      statsRef.current = { intensities: [], classes: [], events: 0 };
      return;
    }

    chunkBusyRef.current = true;

    // ── JSON stats → analytics-service (existing path, fire-and-forget) ──
    if (stats.intensities.length > 0) {
      const avgIntensity = stats.intensities.reduce((a, b) => a + b, 0) / stats.intensities.length;
      const counts: Record<string, number> = {};
      stats.classes.forEach(c => { counts[c] = (counts[c] ?? 0) + 1; });
      const dominant = Object.entries(counts).sort((a, b) => b[1] - a[1])[0]?.[0] ?? 'silence';
      AnalyticsAPI.uploadChunk(sid, {
        chunk_index: idx,
        avg_intensity: Math.round(avgIntensity),
        dominant_class: dominant,
        snore_event_count: stats.events,
      }).catch(err => console.warn('stats upload failed', err));
    }

    // ── Binary audio → ingestion-service ──
    // Stop recorder to get file URI, upload asynchronously, then restart.
    try {
      await recorder.stop();
      const audioUri = (recorder as any).uri as string | undefined;
      if (audioUri) {
        IngestionAPI.uploadBinaryChunk(sid, audioUri, idx, CHUNK_SECONDS)
          .catch(err => console.warn('binary upload failed', err));
      }
    } catch (err) {
      console.warn('recorder cycle failed', err);
    }

    chunkIdxRef.current += 1;
    statsRef.current = { intensities: [], classes: [], events: 0 };
    setChunkCount(c => c + 1);

    // Restart recorder for the next 30s segment (unless we're shutting down).
    if (!stoppingRef.current) {
      try {
        await recorder.prepareToRecordAsync();
        recorder.record();
      } catch (err) {
        console.warn('recorder restart failed', err);
      }
    }

    chunkBusyRef.current = false;
  }, [recorder]);

  // Poll the recorder's current metering value and update live UI state.
  // In Privacy Mode, the on-device TFLite classifier is used instead of the
  // loudness heuristic so snore detection runs without any cloud upload.
  const pollMeter = useCallback(() => {
    const db  = (recorder as any).currentMetering ?? DB_FLOOR;
    const lvl = dbToIntensity(db);

    // Keep a rolling metering history for the on-device classifier
    const hist = meteringHistRef.current;
    hist.push(db);
    if (hist.length > 128) hist.shift();

    let info: SoundInfo;
    if (privacyModeRef.current && onDeviceClassifier.ready) {
      const result = onDeviceClassifier.classifyFromMetering(hist);
      const map: Record<string, { label: string; color: string; icon: keyof typeof Ionicons.glyphMap }> = {
        snoring:   { label: 'Snoring',   color: Colors.accent,    icon: 'volume-high' },
        breathing: { label: 'Breathing', color: Colors.secondary, icon: 'pulse-outline' },
        ambient:   { label: 'Ambient',   color: Colors.textMuted, icon: 'ear-outline' },
        silence:   { label: 'Silence',   color: Colors.textMuted, icon: 'moon-outline' },
      };
      const entry = map[result.dominantClass] ?? map.silence;
      info = {
        label: entry.label,
        cls:   result.dominantClass === 'ambient' ? 'silence' : result.dominantClass,
        color: entry.color,
        icon:  entry.icon,
      };
    } else {
      info = classify(lvl);
    }

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
    Vibration.vibrate(30);
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
        await sleepSenseWS.connect();
        sleepSenseWS.on('chunk.analyzed', (data) => {
          if (data?.chunk_index !== undefined) setChunkCount(data.chunk_index + 1);
        });
        sleepSenseWS.on('session.complete', (data) => {
          if (data?.sleep_quality_score !== undefined) {
            Alert.alert(
              `Session Complete 🌙`,
              `Sleep score: ${data.sleep_quality_score} (${data.sleep_quality_grade})\nSnoring: ${data.snoring_percentage}%`,
            );
          }
        });
      } else {
        sessionIdRef.current = null; // local-only session
      }
      chunkIdxRef.current    = 0;
      chunkTimerRef.current  = 0;
      statsRef.current       = { intensities: [], classes: [], events: 0 };
      meteringHistRef.current = [];

      setElapsed(0);
      setChunkCount(0);
      setPhase('recording');

      await recorder.prepareToRecordAsync();
      recorder.record();

      // Android foreground service: post a persistent notification so the OS
      // does not kill the audio process when the app moves to the background.
      startForegroundAudioNotification().catch(err =>
        console.warn('foreground notification start failed', err)
      );

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
    Vibration.vibrate([0, 20, 60, 20]);
    stoppingRef.current = true;
    setPhase('stopping');
    if (tickTimerRef.current)  { clearInterval(tickTimerRef.current);  tickTimerRef.current  = null; }
    if (meterTimerRef.current) { clearInterval(meterTimerRef.current); meterTimerRef.current = null; }

    const sid = sessionIdRef.current;

    // If a chunk flush is still running (stop/restart cycle), wait briefly for it.
    if (chunkBusyRef.current) {
      await new Promise(res => setTimeout(res, 1500));
    }

    // Upload final partial chunk (binary + stats).
    // After flushChunk, recorder is stopped (stoppingRef prevents restart).
    await flushChunk();

    // If the recorder is still running (e.g. privacy mode), stop it now.
    try { await recorder.stop(); } catch (_) {}

    // Notify ingestion-service that the session has ended (non-blocking).
    if (sid && !privacyModeRef.current) {
      IngestionAPI.endSession(sid, { ended_at: new Date().toISOString() })
        .catch(err => console.warn('ingestion endSession failed', err));
    }

    // Finalise session on analytics-service (source of truth for scores).
    try {
      if (sid) {
        await AnalyticsAPI.endSession(sid);
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

    // Dismiss the foreground service notification now that recording has stopped.
    stopForegroundAudioNotification().catch(err =>
      console.warn('foreground notification stop failed', err)
    );

    sleepSenseWS.disconnect();
    stoppingRef.current  = false;
    chunkBusyRef.current = false;
    sessionIdRef.current = null;
    setPhase('idle');
    setElapsed(0);
    setIntensity(0);
  };

  const fmt = (s: number) =>
    `${String(Math.floor(s / 3600)).padStart(2, '0')}:` +
    `${String(Math.floor((s % 3600) / 60)).padStart(2, '0')}:` +
    `${String(s % 60).padStart(2, '0')}`;

  const isRecording = phase === 'recording';
  const isStopping  = phase === 'stopping';

  const buttonGradient = isRecording ? (['#F87171', '#DC2626'] as const)
                       : isStopping  ? ([Colors.surfaceHigh, Colors.surface] as const)
                       : (Gradients.cta as readonly [string, string, string]);

  return (
    <AuroraBackground style={{ flex: 1 }} intensity={isRecording ? 'bold' : 'soft'}>
      <SafeAreaView style={{ flex: 1 }} edges={['top']}>
        <View style={styles.container}>
          <Text style={styles.title}>{isRecording ? 'Recording' : isStopping ? 'Finalising' : 'Sleep Recording'}</Text>

          {isRecording && (
            <>
              <Text style={styles.duration}>{fmt(elapsed)}</Text>

              {/* Live waveform */}
              <View style={styles.waveform}>
                {bars.map((bar, i) => (
                  <Animated.View
                    key={i}
                    style={[
                      styles.bar,
                      { height: bar, backgroundColor: soundInfo.color, opacity: 0.50 + (i % 4) * 0.12 },
                    ]}
                  />
                ))}
              </View>

              {/* Live detection card */}
              <GlassCard variant="glass" radius={Radii.xl} padding={20} style={{ width: '100%' }} glow="violet">
                <Text style={styles.liveLabel}>Detected Sound</Text>
                <View style={styles.liveClassRow}>
                  <View style={[styles.liveIconWrap, { backgroundColor: soundInfo.color + '24' }]}>
                    <Ionicons name={soundInfo.icon} size={20} color={soundInfo.color} />
                  </View>
                  <Text style={[styles.liveClass, { color: soundInfo.color }]}>{soundInfo.label}</Text>
                </View>
                <View style={styles.intensityBar}>
                  <Animated.View
                    style={[
                      styles.intensityFill,
                      { width: `${intensity}%`, backgroundColor: soundInfo.color },
                    ]}
                  />
                </View>
                <Text style={styles.intensityText}>
                  Intensity {intensity}  ·  {chunkCount} chunk{chunkCount !== 1 ? 's' : ''} saved
                </Text>
                {privacyMode && (
                  <View style={styles.privacyActiveRow}>
                    <Ionicons name="shield-checkmark" size={12} color={Colors.excellent} />
                    <Text style={styles.privacyActive}>Privacy Mode Active — audio stays on device</Text>
                  </View>
                )}
              </GlassCard>
            </>
          )}

          {isStopping && (
            <View style={styles.idleWrap}>
              <View style={styles.idleMoon}>
                <Ionicons name="cloud-upload-outline" size={42} color={Colors.primary} />
              </View>
              <Text style={styles.idleTitle}>Saving session…</Text>
              <Text style={styles.idleSub}>Uploading final data and computing your score.</Text>
            </View>
          )}

          {phase === 'idle' && (
            <View style={styles.idleWrap}>
              <View style={styles.idleMoon}>
                <Ionicons name="moon" size={48} color={Colors.primary} />
              </View>
              <Text style={styles.idleTitle}>Ready to record</Text>
              <Text style={styles.idleSub}>
                Place your phone face-down on your nightstand and tap the button below before you sleep.
              </Text>
            </View>
          )}

          {/* Record / Stop button — three-layer halo for depth */}
          <View style={styles.recordWrap}>
            <Animated.View
              style={[
                styles.recordHaloOuter,
                {
                  backgroundColor: (isRecording ? '#F87171' : Colors.primary) + '14',
                  transform: [{ scale: pulse }],
                },
              ]}
            />
            <Animated.View
              style={[
                styles.recordHaloInner,
                {
                  backgroundColor: (isRecording ? '#F87171' : Colors.primary) + '26',
                  transform: [{ scale: pulse }],
                },
              ]}
            />
            <TouchableOpacity
              onPress={phase === 'idle' ? startRecording : isRecording ? stopRecording : undefined}
              disabled={isStopping}
              activeOpacity={0.85}
            >
              <LinearGradient
                colors={buttonGradient as any}
                start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
                style={[styles.recordBtn, isRecording ? Elevation.glowPink : Elevation.glowViolet]}
              >
                <Ionicons
                  name={isRecording ? 'stop' : isStopping ? 'hourglass-outline' : 'mic'}
                  size={42}
                  color={isStopping ? Colors.textMuted : '#fff'}
                />
              </LinearGradient>
            </TouchableOpacity>
          </View>

          <Text style={styles.btnLabel}>
            {isRecording ? 'Tap to stop recording'
             : isStopping ? 'Saving…'
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
    </AuroraBackground>
  );
}

const styles = StyleSheet.create({
  container:     { flex: 1, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 32, gap: 18 },
  title:         { color: Colors.text, fontSize: 22, fontWeight: '800', letterSpacing: -0.4 },
  duration:      { color: Colors.text, fontSize: 56, fontWeight: '800', letterSpacing: 1, fontVariant: ['tabular-nums'] },
  waveform:      { flexDirection: 'row', alignItems: 'center', gap: 3, height: 64 },
  bar:           { width: 5, borderRadius: 3 },
  liveLabel:     { color: Colors.textMuted, fontSize: 11, marginBottom: 10, letterSpacing: 1.4, textTransform: 'uppercase', fontWeight: '700', textAlign: 'center' },
  liveClassRow:  { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10, marginBottom: 14 },
  liveIconWrap:  { width: 32, height: 32, borderRadius: 16, alignItems: 'center', justifyContent: 'center' },
  liveClass:     { fontSize: 22, fontWeight: '800', letterSpacing: -0.4 },
  intensityBar:  { width: '100%', height: 8, backgroundColor: Colors.surfaceHigh, borderRadius: 4, overflow: 'hidden' },
  intensityFill: { height: '100%', borderRadius: 4 },
  intensityText: { color: Colors.textMuted, fontSize: 12, marginTop: 8, textAlign: 'center', fontWeight: '500' },

  idleWrap:      { alignItems: 'center', gap: 14 },
  idleMoon:      { width: 96, height: 96, borderRadius: 48, backgroundColor: Colors.primary + '14', alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: Colors.primary + '33' },
  idleTitle:     { color: Colors.text, fontSize: 22, fontWeight: '800', letterSpacing: -0.4, marginTop: 4 },
  idleSub:       { color: Colors.textSub, textAlign: 'center', lineHeight: 22, fontSize: 14, maxWidth: 300 },

  recordWrap:    { alignItems: 'center', justifyContent: 'center', marginTop: 8, marginBottom: 4 },
  recordHaloOuter:{ position: 'absolute', width: 180, height: 180, borderRadius: 90 },
  recordHaloInner:{ position: 'absolute', width: 140, height: 140, borderRadius: 70 },
  recordBtn:     { width: 108, height: 108, borderRadius: 54, alignItems: 'center', justifyContent: 'center' },
  btnLabel:      { color: Colors.textSub, fontSize: 13, fontWeight: '600', letterSpacing: 0.2 },

  tipsRow:       { flexDirection: 'row', gap: 14, marginTop: 4, flexWrap: 'wrap', justifyContent: 'center' },
  tip:           { flexDirection: 'row', alignItems: 'center', gap: 5 },
  tipText:       { color: Colors.textSub, fontSize: 12, fontWeight: '500' },

  privacyRow:      { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 4, paddingHorizontal: 14, paddingVertical: 10, backgroundColor: 'rgba(167,139,250,0.06)', borderRadius: Radii.lg, borderWidth: 1, borderColor: Colors.borderSoft, width: '100%' },
  privacyLabel:    { color: Colors.textSub, fontSize: 12, flex: 1, fontWeight: '500' },
  privacyToggle:   { width: 40, height: 22, borderRadius: 11, backgroundColor: Colors.border, justifyContent: 'center', paddingHorizontal: 2 },
  privacyToggleOn: { backgroundColor: Colors.excellent + '55' },
  privacyThumb:    { width: 18, height: 18, borderRadius: 9, backgroundColor: Colors.textMuted },
  privacyThumbOn:  { backgroundColor: Colors.excellent, alignSelf: 'flex-end' },
  privacyActiveRow:{ flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 8, justifyContent: 'center' },
  privacyActive:   { color: Colors.excellent, fontSize: 11, fontWeight: '600' },
});
