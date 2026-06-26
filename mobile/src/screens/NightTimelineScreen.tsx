import React, { useEffect, useRef, useState, useCallback } from 'react';
import { NativeStackScreenProps } from '@react-navigation/native-stack';
import type { HistoryStackParams } from '../navigation/MainNavigator';
import {
  View, Text, StyleSheet, TouchableOpacity, ActivityIndicator,
  FlatList, Dimensions, NativeSyntheticEvent, NativeScrollEvent,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Radii, scoreColor } from '../theme';
import AuroraBackground from '../components/AuroraBackground';
import * as AnalyticsAPI from '../api/analytics.api';
import InteractiveTimelineChart, { TimelineBucket } from '../components/InteractiveTimelineChart';

const { width: SCREEN_W } = Dimensions.get('window');
const CHART_W = SCREEN_W - 72;   // inside the chart card (screen padding + card padding)

type Props = NativeStackScreenProps<HistoryStackParams, 'NightTimeline'>;

export default function NightTimelineScreen({ route, navigation }: Props) {
  const startSessionId = route.params?.sessionId;
  const [sessions, setSessions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [index, setIndex] = useState(0);
  // Per-night timeline cache: sessionId -> buckets (or null while loading).
  const [timelines, setTimelines] = useState<Record<string, TimelineBucket[] | null>>({});
  const listRef = useRef<FlatList>(null);

  // Load the night list (newest first), then jump to the requested night.
  useEffect(() => {
    AnalyticsAPI.getSessions(50)
      .then(res => {
        const list = res.data.sessions ?? [];
        setSessions(list);
        const start = startSessionId ? list.findIndex((s: any) => s.id === startSessionId) : 0;
        if (start > 0) setIndex(start);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [startSessionId]);

  // Fetch the timeline for a night once, caching the result.
  const fetchTimeline = useCallback((sessionId: string) => {
    setTimelines(prev => {
      if (sessionId in prev) return prev;             // already loading/loaded
      AnalyticsAPI.getTimeline(sessionId)
        .then(res => setTimelines(p => ({ ...p, [sessionId]: res.data.buckets ?? [] })))
        .catch(() => setTimelines(p => ({ ...p, [sessionId]: [] })));
      return { ...prev, [sessionId]: null };
    });
  }, []);

  // Prefetch the focused night + its two neighbours so swipes feel instant.
  useEffect(() => {
    if (!sessions.length) return;
    [index - 1, index, index + 1].forEach(i => {
      if (i >= 0 && i < sessions.length) fetchTimeline(sessions[i].id);
    });
  }, [index, sessions, fetchTimeline]);

  // Jump to the requested night once the list + layout are ready.
  useEffect(() => {
    if (!loading && index > 0 && sessions.length > index) {
      requestAnimationFrame(() => listRef.current?.scrollToIndex({ index, animated: false }));
    }
  }, [loading, sessions.length]);   // eslint-disable-line react-hooks/exhaustive-deps

  const onMomentumEnd = (e: NativeSyntheticEvent<NativeScrollEvent>) => {
    const i = Math.round(e.nativeEvent.contentOffset.x / SCREEN_W);
    if (i !== index) setIndex(i);
  };

  const goTo = (i: number) => {
    if (i < 0 || i >= sessions.length) return;
    listRef.current?.scrollToIndex({ index: i, animated: true });
    setIndex(i);
  };

  if (loading) {
    return (
      <AuroraBackground style={styles.center}>
        <ActivityIndicator color={Colors.primary} size="large" />
      </AuroraBackground>
    );
  }

  if (!sessions.length) {
    return (
      <AuroraBackground style={{ flex: 1 }}>
        <SafeAreaView style={[styles.center, { flex: 1 }]} edges={['top']}>
          <Ionicons name="pulse-outline" size={48} color={Colors.textMuted} />
          <Text style={styles.emptyTitle}>No nights to plot yet</Text>
          <Text style={styles.emptySub}>Record a night and your snore timeline will appear here.</Text>
          <TouchableOpacity style={styles.backLink} onPress={() => navigation.goBack()}>
            <Text style={{ color: Colors.primary, fontWeight: '700' }}>Go back</Text>
          </TouchableOpacity>
        </SafeAreaView>
      </AuroraBackground>
    );
  }

  const current = sessions[index];
  const curDate = current?.started_at ? new Date(current.started_at) : null;

  return (
    <AuroraBackground style={{ flex: 1 }}>
      <SafeAreaView style={{ flex: 1 }} edges={['top']}>
        {/* Header — date + carousel position + prev/next fallback */}
        <View style={styles.header}>
          <TouchableOpacity style={styles.iconBtn} onPress={() => navigation.goBack()}>
            <Ionicons name="arrow-back" size={20} color={Colors.text} />
          </TouchableOpacity>
          <View style={{ flex: 1, alignItems: 'center' }}>
            <Text style={styles.title}>Snore Timeline</Text>
            <Text style={styles.date}>
              {curDate ? curDate.toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' }) : ''}
            </Text>
          </View>
          <Text style={styles.counter}>{index + 1}/{sessions.length}</Text>
        </View>

        <View style={styles.navRow}>
          <TouchableOpacity disabled={index === 0} onPress={() => goTo(index - 1)} style={styles.navBtn}>
            <Ionicons name="chevron-back" size={18} color={index === 0 ? Colors.textMuted : Colors.primary} />
            <Text style={[styles.navText, index === 0 && { color: Colors.textMuted }]}>Newer</Text>
          </TouchableOpacity>
          <Text style={styles.swipeHint}>swipe to compare nights</Text>
          <TouchableOpacity disabled={index === sessions.length - 1} onPress={() => goTo(index + 1)} style={styles.navBtn}>
            <Text style={[styles.navText, index === sessions.length - 1 && { color: Colors.textMuted }]}>Older</Text>
            <Ionicons name="chevron-forward" size={18} color={index === sessions.length - 1 ? Colors.textMuted : Colors.primary} />
          </TouchableOpacity>
        </View>

        {/* Night carousel — one night per page, swipe horizontally */}
        <FlatList
          ref={listRef}
          data={sessions}
          horizontal
          pagingEnabled
          showsHorizontalScrollIndicator={false}
          keyExtractor={s => s.id}
          getItemLayout={(_, i) => ({ length: SCREEN_W, offset: SCREEN_W * i, index: i })}
          onMomentumScrollEnd={onMomentumEnd}
          initialNumToRender={2}
          windowSize={3}
          renderItem={({ item }) => (
            <NightPage session={item} buckets={timelines[item.id]} />
          )}
        />
      </SafeAreaView>
    </AuroraBackground>
  );
}

// ── One night page ─────────────────────────────────────────────────────────────

function NightPage({ session, buckets }: { session: any; buckets?: TimelineBucket[] | null }) {
  const score = session.sleep_quality_score;
  return (
    <View style={{ width: SCREEN_W, paddingHorizontal: 20 }}>
      {/* Stat chips */}
      <View style={styles.chips}>
        <Chip label="Score" value={`${Math.round(score ?? 0)}`} color={scoreColor(score)} />
        <Chip label="Snoring" value={`${session.snoring_percentage ?? 0}%`} color={Colors.danger} />
        <Chip label="Avg" value={`${Math.round(session.avg_snore_intensity ?? 0)}`} color={Colors.amber} />
        <Chip label="Peak" value={`${Math.round(session.max_snore_intensity ?? 0)}`} color={Colors.accent} />
      </View>

      {/* Chart card */}
      <View style={styles.chartCard}>
        <Text style={styles.chartTitle}>Snore intensity through the night</Text>
        {buckets === null || buckets === undefined ? (
          <View style={styles.chartLoading}><ActivityIndicator color={Colors.primary} /></View>
        ) : buckets.length === 0 ? (
          <View style={styles.chartLoading}><Text style={styles.muted}>No timeline recorded for this night</Text></View>
        ) : (
          <InteractiveTimelineChart buckets={buckets} startedAt={session.started_at} width={CHART_W} height={210} />
        )}
      </View>
    </View>
  );
}

function Chip({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <View style={styles.chip}>
      <Text style={[styles.chipValue, { color }]}>{value}</Text>
      <Text style={styles.chipLabel}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  center:      { justifyContent: 'center', alignItems: 'center' },
  header:      { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 20, paddingTop: 4, paddingBottom: 8 },
  iconBtn:     { width: 40, height: 40, borderRadius: 20, backgroundColor: 'rgba(167,139,250,0.10)', borderWidth: 1, borderColor: Colors.borderSoft, alignItems: 'center', justifyContent: 'center' },
  title:       { color: Colors.text, fontSize: 17, fontWeight: '800', letterSpacing: -0.3 },
  date:        { color: Colors.textSub, fontSize: 12, marginTop: 2, fontWeight: '500' },
  counter:     { color: Colors.textMuted, fontSize: 13, fontWeight: '700', minWidth: 40, textAlign: 'right' },
  navRow:      { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 20, marginBottom: 12 },
  navBtn:      { flexDirection: 'row', alignItems: 'center', gap: 2, paddingVertical: 4 },
  navText:     { color: Colors.primary, fontWeight: '700', fontSize: 13 },
  swipeHint:   { color: Colors.textMuted, fontSize: 11, fontWeight: '500', fontStyle: 'italic' },
  chips:       { flexDirection: 'row', gap: 8, marginBottom: 16 },
  chip:        { flex: 1, backgroundColor: 'rgba(167,139,250,0.06)', borderRadius: Radii.lg, paddingVertical: 12, alignItems: 'center', borderWidth: 1, borderColor: Colors.borderSoft },
  chipValue:   { fontWeight: '800', fontSize: 18, letterSpacing: -0.4 },
  chipLabel:   { color: Colors.textMuted, fontSize: 10, marginTop: 3, fontWeight: '600', letterSpacing: 0.3 },
  chartCard:   { backgroundColor: 'rgba(167,139,250,0.06)', borderRadius: Radii.xl, padding: 16, borderWidth: 1, borderColor: Colors.borderSoft },
  chartTitle:  { color: Colors.text, fontWeight: '800', fontSize: 14, marginBottom: 14, letterSpacing: -0.2 },
  chartLoading:{ height: 210, alignItems: 'center', justifyContent: 'center' },
  muted:       { color: Colors.textMuted, fontSize: 13 },
  emptyTitle:  { color: Colors.text, fontWeight: '800', fontSize: 16, marginTop: 12 },
  emptySub:    { color: Colors.textMuted, fontSize: 13, textAlign: 'center', maxWidth: 260, lineHeight: 20, marginTop: 6 },
  backLink:    { marginTop: 18, paddingVertical: 8, paddingHorizontal: 16 },
});
