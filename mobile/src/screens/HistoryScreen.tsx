import React, { useEffect, useState, useCallback } from 'react';
import { NativeStackScreenProps } from '@react-navigation/native-stack';
import type { HistoryStackParams } from '../navigation/MainNavigator';
import { View, Text, ScrollView, StyleSheet, TouchableOpacity, ActivityIndicator, RefreshControl, Dimensions } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, scoreColor, Radii } from '../theme';
import AuroraBackground from '../components/AuroraBackground';
import * as AnalyticsAPI from '../api/analytics.api';
import TrendChart from '../components/TrendChart';

const PERIODS = ['7d', '30d', '90d'];
const { width } = Dimensions.get('window');

type Props = NativeStackScreenProps<HistoryStackParams, 'HistoryMain'>;

export default function HistoryScreen({ navigation }: Props) {
  const [period,     setPeriod]     = useState('30d');
  const [trends,     setTrends]     = useState<any>(null);
  const [sessions,   setSessions]   = useState<any[]>([]);
  const [loading,    setLoading]    = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [loadError,  setLoadError]  = useState(false);

  const load = useCallback(async () => {
    setLoadError(false);
    try {
      const [tRes, sRes] = await Promise.all([
        AnalyticsAPI.getTrends(period),
        AnalyticsAPI.getSessions(50),
      ]);
      setTrends(tRes.data);
      setSessions(sRes.data.sessions ?? []);
    } catch { setLoadError(true); } finally { setLoading(false); setRefreshing(false); }
  }, [period]);

  useEffect(() => { load(); }, [load]);

  const onRefresh = () => { setRefreshing(true); load(); };

  if (loading) return (
    <AuroraBackground style={styles.center}>
      <ActivityIndicator color={Colors.primary} size="large" />
    </AuroraBackground>
  );

  const calendarData = (() => {
    const map: Record<string, number> = {};
    (sessions as any[]).forEach(s => {
      if (s.started_at) {
        const d = new Date(s.started_at).toISOString().slice(0, 10);
        map[d] = s.sleep_quality_score ?? 0;
      }
    });
    return map;
  })();

  const calendarDays = (() => {
    const days = [];
    const today = new Date();
    for (let i = 89; i >= 0; i--) {
      const d = new Date(today);
      d.setDate(today.getDate() - i);
      days.push(d.toISOString().slice(0, 10));
    }
    return days;
  })();

  const dayColor = (score?: number) => {
    if (score === undefined) return Colors.surface;
    if (score >= 90) return Colors.excellent;
    if (score >= 75) return Colors.good;
    if (score >= 60) return Colors.fair;
    if (score >= 40) return Colors.poor;
    return Colors.critical;
  };

  return (
    <AuroraBackground style={{ flex: 1 }}>
    <SafeAreaView style={{ flex: 1 }} edges={['top']}>
      <ScrollView
        contentContainerStyle={styles.container}
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.primary} />}
      >
        <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
          <Text style={styles.heading}>Sleep History</Text>
          <TouchableOpacity
            onPress={() => navigation.navigate('Calendar')}
            style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}
            accessibilityLabel="Open Calendar view"
          >
            <Ionicons name="calendar-outline" size={18} color={Colors.primary} />
            <Text style={{ color: Colors.primary, fontSize: 13, fontWeight: '600' }}>Calendar</Text>
          </TouchableOpacity>
        </View>

        {loadError && (
          <View style={styles.errorBanner}>
            <Ionicons name="cloud-offline-outline" size={16} color={Colors.danger} />
            <Text style={styles.errorBannerText}>Failed to load history. Pull down to retry.</Text>
          </View>
        )}

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

        {/* Calendar Heatmap (90 days) */}
        <View style={styles.heatmapCard}>
          <Text style={styles.sectionTitle}>90-Day Heatmap</Text>
          <View style={styles.heatmapGrid}>
            {calendarDays.map(day => {
              const score = calendarData[day];
              return (
                <TouchableOpacity
                  key={day}
                  style={[styles.heatCell, { backgroundColor: score !== undefined ? dayColor(score) + 'CC' : Colors.border }]}
                  onPress={() => {
                    const s = (sessions as any[]).find(x => x.started_at?.startsWith(day));
                    if (s) navigation.navigate('SessionDetail', { sessionId: s.id });
                  }}
                />
              );
            })}
          </View>
          <View style={styles.heatLegend}>
            {[['No data', Colors.border], ['Critical', Colors.critical], ['Poor', Colors.poor], ['Fair', Colors.fair], ['Good', Colors.good], ['Excellent', Colors.excellent]].map(([label, color]) => (
              <View key={label} style={styles.legendItem}>
                <View style={[styles.legendDot, { backgroundColor: color as string }]} />
                <Text style={styles.legendText}>{label}</Text>
              </View>
            ))}
          </View>
        </View>

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
              activeOpacity={0.7}
              onPress={() => navigation.navigate('SessionDetail', { sessionId: s.id })}
            >
              <View style={[styles.scoreBadge, { backgroundColor: scoreColor(s.sleep_quality_score) + '22' }]}>
                <Text style={[styles.scoreNum, { color: scoreColor(s.sleep_quality_score) }]}>
                  {Math.round(s.sleep_quality_score ?? 0)}
                </Text>
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.sessionDate}>
                  {new Date(s.started_at).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })}
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
    </AuroraBackground>
  );
}

const styles = StyleSheet.create({
  center:        { justifyContent: 'center', alignItems: 'center' },
  errorBanner:   { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: Colors.danger + '18', borderRadius: Radii.lg, padding: 12, marginBottom: 16, borderWidth: 1, borderColor: Colors.danger + '33' },
  errorBannerText:{ color: Colors.danger, fontSize: 13, flex: 1 },
  container:    { padding: 20, paddingBottom: 120 },
  heading:      { color: Colors.text, fontSize: 28, fontWeight: '800', marginBottom: 16, letterSpacing: -0.8 },
  periodRow:    { flexDirection: 'row', gap: 6, marginBottom: 20, backgroundColor: 'rgba(31,31,61,0.6)', padding: 4, borderRadius: Radii.lg, borderWidth: 1, borderColor: Colors.borderSoft },
  periodBtn:    { flex: 1, paddingVertical: 9, borderRadius: Radii.md, alignItems: 'center' },
  periodActive: { backgroundColor: Colors.primary },
  periodText:   { color: Colors.textSub, fontWeight: '700', fontSize: 13, letterSpacing: 0.4 },
  summaryCard:  { backgroundColor: 'rgba(167,139,250,0.06)', borderRadius: Radii.xl, padding: 18, marginBottom: 16, borderWidth: 1, borderColor: Colors.borderSoft },
  summaryRow:   { flexDirection: 'row', justifyContent: 'space-around' },
  summaryItem:  { alignItems: 'center' },
  summaryVal:   { color: Colors.text, fontWeight: '800', fontSize: 22, letterSpacing: -0.6 },
  summaryLbl:   { color: Colors.textMuted, fontSize: 11, marginTop: 4, fontWeight: '600', letterSpacing: 0.4 },
  chartCard:    { backgroundColor: 'rgba(167,139,250,0.06)', borderRadius: Radii.xl, padding: 16, marginBottom: 20, borderWidth: 1, borderColor: Colors.borderSoft },
  sectionTitle: { color: Colors.text, fontWeight: '800', fontSize: 15, marginBottom: 12, letterSpacing: -0.2 },
  sessionRow:   { flexDirection: 'row', alignItems: 'center', backgroundColor: 'rgba(167,139,250,0.06)', borderRadius: Radii.lg, padding: 14, marginBottom: 10, gap: 12, borderWidth: 1, borderColor: Colors.borderSoft },
  scoreBadge:   { width: 48, height: 48, borderRadius: 24, alignItems: 'center', justifyContent: 'center' },
  scoreNum:     { fontWeight: '800', fontSize: 16, letterSpacing: -0.4 },
  sessionDate:  { color: Colors.text, fontWeight: '700', fontSize: 14, letterSpacing: -0.2 },
  sessionSub:   { color: Colors.textMuted, fontSize: 12, marginTop: 2, fontWeight: '500' },
  grade:        { fontWeight: '700', fontSize: 11, letterSpacing: 0.6, textTransform: 'uppercase' },
  arrow:        { color: Colors.textMuted, fontSize: 20 },
  emptyState:   { alignItems: 'center', paddingVertical: 48, gap: 10 },
  emptyTitle:   { color: Colors.text, fontWeight: '800', fontSize: 16 },
  emptySub:     { color: Colors.textMuted, fontSize: 13, textAlign: 'center', maxWidth: 260, lineHeight: 20 },
  heatmapCard:  { backgroundColor: 'rgba(167,139,250,0.06)', borderRadius: Radii.xl, padding: 16, marginBottom: 20, borderWidth: 1, borderColor: Colors.borderSoft },
  heatmapGrid:  { flexDirection: 'row', flexWrap: 'wrap', gap: 3, marginBottom: 10 },
  heatCell:     { width: 10, height: 10, borderRadius: 2 },
  heatLegend:   { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  legendItem:   { flexDirection: 'row', alignItems: 'center', gap: 4 },
  legendDot:    { width: 8, height: 8, borderRadius: 2 },
  legendText:   { color: Colors.textMuted, fontSize: 10, fontWeight: '500' },
});
