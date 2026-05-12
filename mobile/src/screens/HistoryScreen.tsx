import React, { useEffect, useState, useCallback } from 'react';
import { View, Text, ScrollView, StyleSheet, TouchableOpacity, ActivityIndicator, RefreshControl, Dimensions } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, scoreColor } from '../theme/colors';
import * as AnalyticsAPI from '../api/analytics.api';
import TrendChart from '../components/TrendChart';

const PERIODS = ['7d', '30d', '90d'];
const { width } = Dimensions.get('window');

export default function HistoryScreen({ navigation }: any) {
  const [period,     setPeriod]     = useState('30d');
  const [trends,     setTrends]     = useState<any>(null);
  const [sessions,   setSessions]   = useState<any[]>([]);
  const [loading,    setLoading]    = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const [tRes, sRes] = await Promise.all([
        AnalyticsAPI.getTrends(period),
        AnalyticsAPI.getSessions(50),
      ]);
      setTrends(tRes.data);
      setSessions(sRes.data);
    } catch {} finally { setLoading(false); setRefreshing(false); }
  }, [period]);

  useEffect(() => { load(); }, [load]);

  const onRefresh = () => { setRefreshing(true); load(); };

  if (loading) return (
    <View style={styles.center}><ActivityIndicator color={Colors.primary} size="large" /></View>
  );

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.bg }}>
      <ScrollView
        contentContainerStyle={styles.container}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.primary} />}
      >
        <Text style={styles.heading}>Sleep History</Text>

        {/* Period selector */}
        <View style={styles.periodRow}>
          {PERIODS.map(p => (
            <TouchableOpacity key={p} onPress={() => setPeriod(p)} style={[styles.periodBtn, period === p && styles.periodActive]}>
              <Text style={[styles.periodText, period === p && { color: Colors.bg }]}>{p}</Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Summary */}
        {trends?.summary && (
          <View style={styles.summaryCard}>
            <View style={styles.summaryRow}>
              <View style={styles.summaryItem}>
                <Text style={styles.summaryVal}>{trends.summary.avg_quality_score}</Text>
                <Text style={styles.summaryLbl}>avg score</Text>
              </View>
              <View style={styles.summaryItem}>
                <Text style={[styles.summaryVal, { color: Colors.danger }]}>{trends.summary.avg_snoring_percentage}%</Text>
                <Text style={styles.summaryLbl}>avg snoring</Text>
              </View>
              <View style={styles.summaryItem}>
                <Text style={[styles.summaryVal, {
                  color: trends.summary.trend_direction === 'improving' ? Colors.excellent :
                         trends.summary.trend_direction === 'declining' ? Colors.danger : Colors.amber,
                }]}>
                  {trends.summary.trend_direction === 'improving' ? '↑' : trends.summary.trend_direction === 'declining' ? '↓' : '→'}
                  {' '}{trends.summary.trend_direction}
                </Text>
                <Text style={styles.summaryLbl}>trend</Text>
              </View>
            </View>
          </View>
        )}

        {/* Trend chart */}
        {trends?.data_points?.length > 0 && (
          <View style={styles.chartCard}>
            <Text style={styles.sectionTitle}>Quality Score Trend</Text>
            <TrendChart data={trends.data_points} width={width - 56} height={150} />
          </View>
        )}

        {/* Session list */}
        <Text style={styles.sectionTitle}>All Sessions</Text>
        {sessions.length === 0 ? (
          <View style={styles.emptyState}>
            <Ionicons name="moon-outline" size={48} color={Colors.textMuted} />
            <Text style={styles.emptyTitle}>No sessions recorded yet</Text>
            <Text style={styles.emptySub}>Your sleep history will appear here after your first recording.</Text>
          </View>
        ) : (
          sessions.map(s => (
            <TouchableOpacity
              key={s.id}
              style={styles.sessionRow}
              onPress={() => navigation.navigate('SessionDetail', { sessionId: s.id })}
            >
              <View style={[styles.scoreBadge, { backgroundColor: scoreColor(s.sleep_quality_score) + '22' }]}>
                <Text style={[styles.scoreNum, { color: scoreColor(s.sleep_quality_score) }]}>
                  {Math.round(s.sleep_quality_score ?? 0)}
                </Text>
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.sessionDate}>
                  {new Date(s.started_at).toLocaleDateString('en-IN', { weekday: 'short', month: 'short', day: 'numeric' })}
                </Text>
                <Text style={styles.sessionSub}>
                  {Math.floor((s.duration_minutes ?? 0) / 60)}h {(s.duration_minutes ?? 0) % 60}m · Snoring {s.snoring_percentage}%
                </Text>
              </View>
              <Text style={[styles.grade, { color: scoreColor(s.sleep_quality_score) }]}>{s.sleep_quality_grade}</Text>
              <Text style={styles.arrow}>›</Text>
            </TouchableOpacity>
          ))
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  center:       { flex: 1, backgroundColor: Colors.bg, justifyContent: 'center', alignItems: 'center' },
  container:    { padding: 20, paddingBottom: 40 },
  heading:      { color: Colors.text, fontSize: 22, fontWeight: '700', marginBottom: 16 },
  periodRow:    { flexDirection: 'row', gap: 8, marginBottom: 20 },
  periodBtn:    { flex: 1, paddingVertical: 8, borderRadius: 10, borderWidth: 1, borderColor: Colors.border, alignItems: 'center' },
  periodActive: { backgroundColor: Colors.primary, borderColor: Colors.primary },
  periodText:   { color: Colors.textSub, fontWeight: '600' },
  summaryCard:  { backgroundColor: Colors.surface, borderRadius: 16, padding: 16, marginBottom: 16, borderWidth: 1, borderColor: Colors.border },
  summaryRow:   { flexDirection: 'row', justifyContent: 'space-around' },
  summaryItem:  { alignItems: 'center' },
  summaryVal:   { color: Colors.text, fontWeight: '800', fontSize: 20 },
  summaryLbl:   { color: Colors.textMuted, fontSize: 11, marginTop: 2 },
  chartCard:    { backgroundColor: Colors.surface, borderRadius: 16, padding: 16, marginBottom: 20, borderWidth: 1, borderColor: Colors.border },
  sectionTitle: { color: Colors.text, fontWeight: '700', fontSize: 16, marginBottom: 12 },
  sessionRow:   { flexDirection: 'row', alignItems: 'center', backgroundColor: Colors.surface, borderRadius: 14, padding: 14, marginBottom: 10, gap: 12, borderWidth: 1, borderColor: Colors.border },
  scoreBadge:   { width: 48, height: 48, borderRadius: 24, alignItems: 'center', justifyContent: 'center' },
  scoreNum:     { fontWeight: '800', fontSize: 16 },
  sessionDate:  { color: Colors.text, fontWeight: '600', fontSize: 14 },
  sessionSub:   { color: Colors.textMuted, fontSize: 12, marginTop: 2 },
  grade:        { fontWeight: '600', fontSize: 12 },
  arrow:        { color: Colors.textMuted, fontSize: 20 },
  emptyState:   { alignItems: 'center', paddingVertical: 48, gap: 10 },
  emptyTitle:   { color: Colors.text, fontWeight: '700', fontSize: 16 },
  emptySub:     { color: Colors.textMuted, fontSize: 13, textAlign: 'center', maxWidth: 260, lineHeight: 20 },
});
