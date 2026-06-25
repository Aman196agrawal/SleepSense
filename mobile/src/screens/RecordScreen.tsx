import React, { useState, useEffect, useRef, useCallback } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { View, Text, StyleSheet, TouchableOpacity, Animated, Alert, Platform, AppState, AppStateStatus, Vibration, Dimensions } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { useAudioRecorder, type AudioDataEvent } from '@siteed/expo-audio-studio';
import { AudioModule } from 'expo-audio';
import * as FileSystem from 'expo-file-system/legacy';
import { BottomTabScreenProps } from '@react-navigation/bottom-tabs';
import { Colors, Radii, Elevation, Gradients } from '../theme';
import type { MainTabParams } from '../navigation/MainNavigator';
import AuroraBackground from '../components/AuroraBackground';
import GlassCard from '../components/GlassCard';
import { LiveSpectrogram, type LiveSpectrogramHandle } from '../components/LiveSpectrogram';
import {
  MelSpectrogramStreamer, base64ToBytes, pcm16BytesToFloat32, MEL_DISPLAY, SR,
} from '../ml/spectrogram';
import { encodeWavBase64 } from '../ml/wav';
import * as AnalyticsAPI from '../api/analytics.api';
import * as IngestionAPI from '../api/ingestion.api';
import { sleepSenseWS } from '../api/ws';
import { onDeviceClassifier } from '../ml/OnDeviceClassifier';

// Live audio level is now derived from the PCM stream as RMS dBFS (0 dB = full
// scale, ~-80 dB = silence) instead of the recorder's metering API. Map the
// useful snore band [-60, -5] dBFS → [0, 100] intensity.
// NOTE: this is still loudness-based heuristic detection; the CNN classifier is
// on the roadmap (Privacy Mode already runs the on-device TFLite model).
const DB_FLOOR = -60;
const DB_CEIL  = -5;
const dbToIntensity = (db: number): number =>
  Math.round(Math.max(0, Math.min(100, ((db - DB_FLOOR) / (DB_CEIL - DB_FLOOR)) * 100)));

/** RMS level of a PCM frame as dBFS. */
const rmsDbfs = (pcm: Float32Array): number => {
  if (pcm.length === 0) return DB_FLOOR;
  let sum = 0;
  for (let i = 0; i < pcm.length; i++) sum += pcm[i] * pcm[i];
  const rms = Math.sqrt(sum / pcm.length);
  return 20 * Math.log10(rms + 1e-7);
};

type SoundInfo = { label: string; cls: string; color: string; icon: keyof typeof Ionicons.glyphMap };
const classify = (lvl: number): SoundInfo => {
  if (lvl < 8)  return { label: 'Silence',      cls: 'silence',   color: Colors.textMuted, icon: 'moon-outline' };
  if (lvl < 30) return { label: 'Breathing',    cls: 'breathing', color: Colors.secondary, icon: 'pulse-outline' };
  if (lvl < 65) return { label: 'Snoring',      cls: 'snoring',   color: Colors.accent,    icon: 'volume-high' };
  return               { label: 'Loud Snoring', cls: 'snoring',   color: Colors.danger,    icon: 'volume-high' };
};

const CHUNK_SECONDS    = 30;
const METER_POLL_MS    = 200;

const { width: SCREEN_W } = Dimensions.get('window');
const SPEC_W = Math.round(SCREEN_W - 64);
const SPEC_H = 150;

type Phase = 'idle' | 'recording' | 'stopping';

type Props = BottomTabScreenProps<MainTabParams, 'Record'>;

export default function RecordScreen({ navigation }: Props) {
  const [phase, setPhase]       = useState<Phase>('idle');
  const [elapsed, setElapsed]   = useState(0);
  const [intensity, setIntensity] = useState(0);
  const [soundInfo, setSoundInfo] = useState<SoundInfo>({ label: 'Silence', cls: 'silence', color: Colors.textMuted, icon: 'moon-outline' });
  const [chunkCount, setChunkCount] = useState(0);
  const [privacyMode, setPrivacyMode] = useState(false);

  // Continuous PCM recorder (one stream → live spectrogram + metering + chunking).
  const { startRecording, stopRecording } = useAudioRecorder();

  // Live spectrogram pipeline
  const streamerRef = useRef(new MelSpectrogramStreamer(MEL_DISPLAY));
  const specRef     = useRef<LiveSpectrogramHandle>(null);

  // Refs that survive re-renders during long sessions
  const privacyModeRef   = useRef(false);
  const sessionIdRef     = useRef<string | null>(null);
  const uploadTokenRef   = useRef<string | null>(null);
  const chunkIdxRef      = useRef(0);
  const chunkTimerRef    = useRef(0);
  const tickTimerRef     = useRef<ReturnType<typeof setInterval> | null>(null);
  const meterTimerRef    = useRef<ReturnType<typeof setInterval> | null>(null);
  const stoppingRef      = useRef(false);
  const chunkBusyRef     = useRef(false);
  const appStateRef      = useRef<AppStateStatus>(AppState.currentState);
  const wsUnsubsRef      = useRef<(() => void)[]>([]);
  const actualSampleRateRef = useRef<number>(SR);
  // Raw PCM16 bytes accumulated since the last chunk flush (for WAV assembly).
  const pcmBufRef        = useRef<Uint8Array[]>([]);
  // Most recent RMS dBFS reading, sampled by the UI/stats tick.
  const latestDbRef      = useRef<number>(DB_FLOOR);
  // Rolling window of dBFS readings fed to the on-device TFLite classifier
  const meteringHistRef  = useRef<number[]>([]);
  const statsRef         = useRef<{ intensities: number[]; classes: string[]; events: number }>({
    intensities: [], classes: [], events: 0,
  });

  const pulse = useRef(new Animated.Value(1)).current;

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
    }
  }, [phase, pulse]);

  // Cleanup on unmount: kill any in-flight timers.
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

  // Load saved privacy mode preference on mount
  useEffect(() => {
    AsyncStorage.getItem('privacyMode').then(val => {
      if (val === 'true') setPrivacyMode(true);
    });
  }, []);

  // Pre-load the TFLite model as soon as Privacy Mode is enabled so it is
  // ready before the user starts recording.
  useEffect(() => {
    if (privacyMode && !onDeviceClassifier.ready) {
      onDeviceClassifier.load();
    }
  }, [privacyMode]);

  // Continuous PCM callback: drive the live spectrogram, track the live level,
  // and accumulate raw bytes for the next 30s chunk upload.
  const onAudioStream = useCallback(async (event: AudioDataEvent) => {
    try {
      if (typeof event.data !== 'string') {
        // Web delivers a typed array; native (our target) delivers base64.
        const pcmWeb = Float32Array.from(event.data as Float32Array);
        const colsWeb = streamerRef.current.push(pcmWeb);
        if (colsWeb.length) specRef.current?.pushColumns(colsWeb);
        latestDbRef.current = rmsDbfs(pcmWeb);
        return;
      }
      const bytes = base64ToBytes(event.data);          // raw PCM16 LE
      const pcm = pcm16BytesToFloat32(bytes);
      const cols = streamerRef.current.push(pcm);
      if (cols.length) specRef.current?.pushColumns(cols);
      latestDbRef.current = rmsDbfs(pcm);
      // Only buffer audio for upload in a non-private, server-backed session.
      if (!privacyModeRef.current && sessionIdRef.current) pcmBufRef.current.push(bytes);
    } catch (err) {
      console.warn('audio stream handler failed', err);
    }
  }, []);

  // Assemble the buffered PCM into a 30s WAV and upload it (binary → ingestion),
  // plus post the aggregated stats JSON → analytics. No recorder stop/restart.
  const flushChunk = useCallback(async () => {
    if (chunkBusyRef.current) return; // previous chunk still uploading — skip this tick
    const sid   = sessionIdRef.current;
    const idx   = chunkIdxRef.current;
    const stats = statsRef.current;
    if (!sid || privacyModeRef.current) {
      statsRef.current = { intensities: [], classes: [], events: 0 };
      pcmBufRef.current = [];
      return;
    }

    chunkBusyRef.current = true;

    // ── JSON stats → analytics-service (fire-and-forget) ──
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
    // Assemble a discrete WAV from the bytes streamed over the last ~30s, write
    // it to a temp file, upload, then delete. The recorder keeps running, so the
    // stream is gapless (unlike the old stop/restart approach).
    const pcmChunks = pcmBufRef.current;
    pcmBufRef.current = [];
    if (pcmChunks.length > 0) {
      try {
        const b64 = encodeWavBase64(pcmChunks, actualSampleRateRef.current, 1, 16);
        const uri = `${FileSystem.cacheDirectory}chunk_${idx}.wav`;
        await FileSystem.writeAsStringAsync(uri, b64, { encoding: FileSystem.EncodingType.Base64 });
        // Binary upload is optional — it feeds the server-side ML pipeline. When
        // ingestion-service isn't running the request fails; the session still
        // saves via analytics, so log at warn level. Clean up the temp file after.
        IngestionAPI.uploadBinaryChunk(sid, uri, idx, CHUNK_SECONDS, uploadTokenRef.current)
          .catch(err => console.warn('binary upload skipped (ingestion-service unavailable)', err?.message ?? err))
          .finally(() => { FileSystem.deleteAsync(uri, { idempotent: true }).catch(() => {}); });
      } catch (err) {
        console.warn('chunk assembly failed', err);
      }
    }

    chunkIdxRef.current += 1;
    statsRef.current = { intensities: [], classes: [], events: 0 };
    setChunkCount(c => c + 1);
    chunkBusyRef.current = false;
  }, []);

  // Sample the latest live level for the UI + per-tick stats. In Privacy Mode the
  // on-device TFLite classifier replaces the loudness heuristic so detection runs
  // without any cloud upload.
  const sampleTick = useCallback(() => {
    const db  = latestDbRef.current;
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

    const s = statsRef.current;
    const wasSnoring = s.classes[s.classes.length - 1] === 'snoring';
    s.intensities.push(lvl);
    s.classes.push(info.cls);
    if (info.cls === 'snoring' && !wasSnoring) s.events += 1;
  }, []);

  const startRecordingSession = async () => {
    Vibration.vibrate(30);
    try {
      // Request the mic permission explicitly (app-level on Android/iOS, so this
      // also satisfies the audio-studio recorder) and keep the friendly prompt.
      const { granted } = await AudioModule.requestRecordingPermissionsAsync();
      if (!granted) {
        Alert.alert(
          'Microphone required',
          'Please allow microphone access in your device settings to record sleep audio.'
        );
        setPhase('idle');
        return;
      }

      privacyModeRef.current = privacyMode;
      if (!privacyMode) {
        const res = await AnalyticsAPI.startSession();
        sessionIdRef.current = res.data.session_id;
        // Capability token authorising ingestion-service chunk uploads for this session.
        uploadTokenRef.current = res.data.upload_token ?? null;
        await sleepSenseWS.connect();
        wsUnsubsRef.current = [
          sleepSenseWS.on('chunk.analyzed', (data) => {
            if (data?.chunk_index !== undefined) setChunkCount(data.chunk_index + 1);
          }),
          sleepSenseWS.on('session.complete', (data) => {
            if (data?.sleep_quality_score !== undefined) {
              Alert.alert(
                `Session Complete 🌙`,
                `Sleep score: ${data.sleep_quality_score} (${data.sleep_quality_grade})\nSnoring: ${data.snoring_percentage}%`,
              );
            }
          }),
        ];
      } else {
        sessionIdRef.current = null; // local-only session
      }
      chunkIdxRef.current     = 0;
      chunkTimerRef.current   = 0;
      statsRef.current        = { intensities: [], classes: [], events: 0 };
      meteringHistRef.current = [];
      pcmBufRef.current       = [];
      latestDbRef.current     = DB_FLOOR;
      streamerRef.current.reset();
      specRef.current?.clear();

      setElapsed(0);
      setChunkCount(0);
      setPhase('recording');

      // One continuous PCM stream. The library runs its own Android foreground
      // service (audioFocusStrategy 'background' + showNotification) so the OS
      // does not kill the process during an all-night session.
      const res = await startRecording({
        sampleRate: SR,
        channels: 1,
        encoding: 'pcm_16bit',
        interval: 100,                 // emit PCM ~10×/sec
        keepAwake: true,
        showNotification: true,
        notification: {
          title: 'SleepSense',
          text: 'Recording your sleep…',
          android: { channelId: 'sleepsense-recording', channelName: 'Sleep Recording' },
        },
        android: { audioFocusStrategy: 'background' },
        ios: { audioSession: { category: 'PlayAndRecord', mode: 'Measurement', categoryOptions: ['MixWithOthers', 'DefaultToSpeaker'] } },
        output: { primary: { enabled: false } },   // streaming-only; we assemble chunks in JS
        onAudioStream,
      });
      actualSampleRateRef.current = res.sampleRate ?? SR;
      if (res.sampleRate && res.sampleRate !== SR) {
        // The spectrogram filterbank assumes SR; a device override would shift pitch.
        console.warn(`[RecordScreen] device gave ${res.sampleRate}Hz, pipeline assumes ${SR}Hz`);
      }

      meterTimerRef.current = setInterval(sampleTick, METER_POLL_MS);

      tickTimerRef.current = setInterval(() => {
        setElapsed(e => e + 1);
        chunkTimerRef.current += 1;

        if (chunkTimerRef.current >= CHUNK_SECONDS) {
          chunkTimerRef.current = 0;
          flushChunk().catch(err => console.error('chunk flush failed', err));
        }
      }, 1000);
    } catch (err: any) {
      wsUnsubsRef.current.forEach(u => u());
      wsUnsubsRef.current = [];
      if (tickTimerRef.current)  { clearInterval(tickTimerRef.current);  tickTimerRef.current  = null; }
      if (meterTimerRef.current) { clearInterval(meterTimerRef.current); meterTimerRef.current = null; }
      try { await stopRecording(); } catch (_) {}
      const msg = /permission|denied|microphone/i.test(String(err?.message ?? ''))
        ? 'Please allow microphone access in your device settings to record sleep audio.'
        : (err?.message ?? 'Could not start recording.');
      Alert.alert(/permission|denied|microphone/i.test(String(err?.message ?? '')) ? 'Microphone required' : 'Error', msg);
      setPhase('idle');
    }
  };

  const stopRecordingSession = async () => {
    Vibration.vibrate([0, 20, 60, 20]);
    stoppingRef.current = true;
    setPhase('stopping');
    if (tickTimerRef.current)  { clearInterval(tickTimerRef.current);  tickTimerRef.current  = null; }
    if (meterTimerRef.current) { clearInterval(meterTimerRef.current); meterTimerRef.current = null; }

    const sid = sessionIdRef.current;

    // Wait for any in-progress chunk upload to finish before flushing the final chunk.
    await new Promise<void>((resolve) => {
      if (!chunkBusyRef.current) { resolve(); return; }
      const check = setInterval(() => {
        if (!chunkBusyRef.current) { clearInterval(check); resolve(); }
      }, 100);
      setTimeout(() => { clearInterval(check); resolve(); }, 30000); // 30 s safety cap
    });

    // Stop the recorder first so no more bytes stream in, then upload whatever
    // remains in the buffer as the final partial chunk.
    try { await stopRecording(); } catch (_) {}
    await flushChunk();

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
      console.error('endSession failed', err);
      Alert.alert('Saved', 'Session ended.');
    }

    wsUnsubsRef.current.forEach(u => u());
    wsUnsubsRef.current = [];
    sleepSenseWS.disconnect();
    stoppingRef.current  = false;
    chunkBusyRef.current = false;
    sessionIdRef.current = null;
    uploadTokenRef.current = null;
    pcmBufRef.current = [];
    specRef.current?.clear();
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

              {/* Live mel-spectrogram (x = time, y = frequency, colour = energy) */}
              <LiveSpectrogram
                ref={specRef}
                nMels={MEL_DISPLAY}
                width={SPEC_W}
                height={SPEC_H}
                style={styles.spec}
              />

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
              onPress={phase === 'idle' ? startRecordingSession : isRecording ? stopRecordingSession : undefined}
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
                  onPress={() => {
                    const next = !privacyMode;
                    setPrivacyMode(next);
                    AsyncStorage.setItem('privacyMode', next ? 'true' : 'false');
                  }}
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
  spec:          { marginVertical: 4 },
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
