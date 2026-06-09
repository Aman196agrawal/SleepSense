import React, { useEffect, useState } from 'react';
import { View, Text, ScrollView, StyleSheet, TouchableOpacity, ActivityIndicator, Dimensions } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Radii } from '../theme';
import AuroraBackground from '../components/AuroraBackground';
import GlassCard from '../components/GlassCard';
import * as AnalyticsAPI from '../api/analytics.api';
import ScoreRing    from '../components/ScoreRing';
import StatCard     from '../components/StatCard';
import InsightCard  from '../components/InsightCard';
import ClassDonut          from '../components/ClassDonut';
import StackedAreaTimeline from '../components/StackedAreaTimeline';

const SCREEN_WIDTH = Dimensions.get('window').width;

export default function SessionDetailScreen({ route, navigation }: any) {
  const { sessionId } = route.params;
  const [session,  setSession]  = useState<any>(null);
  const [timeline, setTimeline] = useState<any[]>([]);
  const [insights, setInsights] = useState<any[]>([]);
  const [loading,  setLoading]  = useState(true);

  useEffect(() => {
    Promise.all([
      AnalyticsAPI.getSession(sessionId),
      AnalyticsAPI.getTimeline(sessionId),
      AnalyticsAPI.getInsights(),
    ]).then(([s, t, i]) => {
      setSession(s.data);
      setTimeline(t.data.buckets ?? []);
      setInsights(i.data.filter((ins: any) => ins.session_id === sessionId).slice(0, 3));
    }).catch(() => {}).finally(() => setLoading(false));
  }, [sessionId]);

  if (loading) return (
    <View style={styles.center}><ActivityIndicator color={Colors.primary} size="large" /></View>
  );
  if (!session) return (
    <View style={styles.center}><Text style={{ color: Colors.textSub }}>Session not found</Text></View>
  );

  const date = new Date(session.started_at);

  return (
    <AuroraBackground style={{ flex: 1 }}>
      <SafeAreaView style={{ flex: 1 }} edges={['top']}>
        <ScrollView contentContainerStyle={styles.container} showsVerticalScrollIndicator={false}>
          <View style={styles.header}>
            <TouchableOpacity style={styles.backBtn} onPress={() => navigation.goBack()}>
              <Ionicons name="arrow-back" size={20} color={Colors.text} />
            </TouchableOpacity>
            <View style={{ flex: 1, marginLeft: 12 }}>
              <Text style={styles.title}>Sleep Report</Text>
              <Text style={styles.date}>{date.toLocaleDateString('en-IN', { weekday: 'long', month: 'long', day: 'numeric' })}</Text>
            </View>
          </View>

          {/* Score */}
          <GlassCard variant="hero" glow="violet" radius={Radii.xxl} padding={24} style={{ alignItems: 'center', marginBottom: 20 }}>
            <ScoreRing score={session.sleep_quality_score ?? 0} grade={session.sleep_quality_grade} size={200} />
          </GlassCard>

        {/* Stats */}
        <View style={styles.statsGrid}>
          <StatCard icon="time-outline"        label="Duration"          value={`${Math.floor((session.duration_minutes ?? 0) / 60)}h ${(session.duration_minutes ?? 0) % 60}m`} color={Colors.secondary} />
          <StatCard icon="volume-high-outline" label="Snoring"           value={`${session.snoring_percentage ?? 0}%`}   color={Colors.danger} />
          <StatCard icon="flash-outline"       label="Avg Intensity"     value={`${Math.round(session.avg_snore_intensity ?? 0)}`} color={Colors.amber} />
          <StatCard icon="trending-up-outline" label="Events / hr"       value={`${session.snore_events_per_hour ?? 0}`} color={Colors.fair} />
        </View>

        {/* Score Breakdown (FR-SCORE-002) */}
        {session.sleep_quality_score !== undefined && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Score Breakdown</Text>
            <View style={styles.breakdownCard}>
              {(() => {
                const snoreRatio   = (session.snoring_percentage ?? 0) / 100;
                const snoringImpact  = Math.round(snoreRatio * 40);
                const intensityPenalty = Math.round((session.avg_snore_intensity ?? 0) / 100 * 25);
                const hours          = (session.duration_minutes ?? 0) / 60;
                const interruptions  = Math.round((session.snore_events_per_hour ?? 0) * hours);
                const interruptionPenalty = Math.min(interruptions * 2, 20);
                const durationPenalty = session.duration_minutes < 360
                  ? Math.round(Math.max(0, (360 - (session.duration_minutes ?? 0)) / 360 * 15))
                  : 0;

                const items = [
                  { label: 'Snoring time',   penalty: snoringImpact,    desc: `${session.snoring_percentage ?? 0}% of the night` },
                  { label: 'Snore intensity',penalty: intensityPenalty, desc: `Avg intensity ${Math.round(session.avg_snore_intensity ?? 0)}` },
                  { label: 'Interruptions',  penalty: interruptionPenalty, desc: `~${interruptions} events` },
                  { label: 'Sleep duration', penalty: durationPenalty,  desc: durationPenalty > 0 ? 'Less than 6 hours' : 'Sufficient duration' },
                ];

                return items.map(item => (
                  <View key={item.label} style={styles.breakdownRow}>
                    <View style={{ flex: 1 }}>
                      <Text style={styles.breakdownLabel}>{item.label}</Text>
                      <Text style={styles.breakdownDesc}>{item.desc}</Text>
                    </View>
                    <Text style={[styles.breakdownPenalty, { color: item.penalty > 0 ? Colors.danger : Colors.excellent }]}>
                      {item.penalty > 0 ? `-${item.penalty}` : '0'} pts
                    </Text>
                  </View>
                ));
              })()}
            </View>
          </View>
        )}

        {/* Sound Distribution — donut */}
        {timeline.length > 0 && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Sound Distribution</Text>
            <View style={styles.chartCard}>
              <ClassDonut buckets={timeline} size={150} />
            </View>
          </View>
        )}

        {/* Sound Composition Over Night — stacked area */}
        {timeline.length > 0 && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Sound Composition Over Night</Text>
            <View style={styles.chartCard}>
              <StackedAreaTimeline
                buckets={timeline}
                width={SCREEN_WIDTH - 72}
                height={150}
              />
            </View>
          </View>
        )}

        {/* Insights */}
        {insights.length > 0 && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Insights</Text>
            {insights.map(ins => (
              <InsightCard key={ins.id} title={ins.title} body={ins.body} type={ins.insight_type} />
            ))}
          </View>
        )}
        </ScrollView>
      </SafeAreaView>
    </AuroraBackground>
  );
}

const styles = StyleSheet.create({
  center:      { flex: 1, backgroundColor: Colors.bg, justifyContent: 'center', alignItems: 'center' },
  container:   { padding: 20, paddingBottom: 120 },
  header:      { flexDirection: 'row', alignItems: 'center', marginBottom: 24 },
  backBtn:     { width: 40, height: 40, borderRadius: 20, backgroundColor: 'rgba(167,139,250,0.10)', borderWidth: 1, borderColor: Colors.borderSoft, alignItems: 'center', justifyContent: 'center' },
  title:       { color: Colors.text, fontSize: 20, fontWeight: '800', letterSpacing: -0.4 },
  date:        { color: Colors.textSub, fontSize: 13, marginTop: 2, fontWeight: '500' },
  scoreWrap:   { alignItems: 'center', marginBottom: 24 },
  statsGrid:   { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginBottom: 20 },
  section:     { marginBottom: 22 },
  sectionTitle:{ color: Colors.text, fontWeight: '800', fontSize: 16, marginBottom: 12, letterSpacing: -0.2 },
  chartCard:        { backgroundColor: 'rgba(167,139,250,0.06)', borderRadius: Radii.xl, padding: 16, borderWidth: 1, borderColor: Colors.borderSoft },
  breakdownCard:    { backgroundColor: 'rgba(167,139,250,0.06)', borderRadius: Radii.lg, padding: 16, borderWidth: 1, borderColor: Colors.borderSoft, gap: 12 },
  breakdownRow:     { flexDirection: 'row', alignItems: 'center' },
  breakdownLabel:   { color: Colors.text, fontWeight: '700', fontSize: 13, letterSpacing: -0.2 },
  breakdownDesc:    { color: Colors.textMuted, fontSize: 11, marginTop: 2, fontWeight: '500' },
  breakdownPenalty: { fontWeight: '800', fontSize: 14, minWidth: 52, textAlign: 'right', letterSpacing: -0.2 },
});
