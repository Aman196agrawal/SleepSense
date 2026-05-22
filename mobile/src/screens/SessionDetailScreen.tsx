import React, { useEffect, useState } from 'react';
import { View, Text, ScrollView, StyleSheet, TouchableOpacity, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors } from '../theme/colors';
import * as AnalyticsAPI from '../api/analytics.api';
import ScoreRing    from '../components/ScoreRing';
import StatCard     from '../components/StatCard';
import TimelineChart from '../components/TimelineChart';
import InsightCard  from '../components/InsightCard';

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
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.bg }}>
      <ScrollView contentContainerStyle={styles.container}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => navigation.goBack()}>
            <Ionicons name="arrow-back" size={24} color={Colors.text} />
          </TouchableOpacity>
          <View style={{ flex: 1, marginLeft: 12 }}>
            <Text style={styles.title}>Sleep Report</Text>
            <Text style={styles.date}>{date.toLocaleDateString('en-IN', { weekday: 'long', month: 'long', day: 'numeric' })}</Text>
          </View>
        </View>

        {/* Score */}
        <View style={styles.scoreWrap}>
          <ScoreRing score={session.sleep_quality_score ?? 0} grade={session.sleep_quality_grade} size={180} />
        </View>

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

        {/* Timeline */}
        {timeline.length > 0 && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Snoring Timeline</Text>
            <View style={styles.legendRow}>
              {[['#F43F5E','Snoring'],['#3D8EF0','Breathing'],['#F59E0B','Ambient'],['#1E3A5F','Silence']].map(([c, l]) => (
                <View key={l} style={styles.legendItem}>
                  <View style={[styles.legendDot, { backgroundColor: c }]} />
                  <Text style={styles.legendText}>{l}</Text>
                </View>
              ))}
            </View>
            <TimelineChart buckets={timeline} height={110} />
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
  );
}

const styles = StyleSheet.create({
  center:      { flex: 1, backgroundColor: Colors.bg, justifyContent: 'center', alignItems: 'center' },
  container:   { padding: 20, paddingBottom: 40 },
  header:      { flexDirection: 'row', alignItems: 'center', marginBottom: 28 },
  title:       { color: Colors.text, fontSize: 18, fontWeight: '700' },
  date:        { color: Colors.textSub, fontSize: 13, marginTop: 2 },
  scoreWrap:   { alignItems: 'center', marginBottom: 24 },
  statsGrid:   { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 24 },
  section:     { marginBottom: 24 },
  sectionTitle:{ color: Colors.text, fontWeight: '700', fontSize: 16, marginBottom: 12 },
  legendRow:   { flexDirection: 'row', flexWrap: 'wrap', gap: 12, marginBottom: 8 },
  legendItem:  { flexDirection: 'row', alignItems: 'center', gap: 4 },
  legendDot:   { width: 8, height: 8, borderRadius: 4 },
  legendText:  { color: Colors.textMuted, fontSize: 11 },
  breakdownCard:    { backgroundColor: Colors.surface, borderRadius: 14, padding: 16, borderWidth: 1, borderColor: Colors.border, gap: 12 },
  breakdownRow:     { flexDirection: 'row', alignItems: 'center' },
  breakdownLabel:   { color: Colors.text, fontWeight: '600', fontSize: 13 },
  breakdownDesc:    { color: Colors.textMuted, fontSize: 11, marginTop: 2 },
  breakdownPenalty: { fontWeight: '700', fontSize: 14, minWidth: 52, textAlign: 'right' },
});
