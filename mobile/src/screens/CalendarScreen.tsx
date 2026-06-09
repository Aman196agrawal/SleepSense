import React, { useCallback, useEffect, useRef, useState } from 'react';
import { NativeStackScreenProps } from '@react-navigation/native-stack';
import type { HistoryStackParams } from '../navigation/MainNavigator';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  ActivityIndicator, RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Radii } from '../theme';
import AuroraBackground from '../components/AuroraBackground';
import * as AnalyticsAPI from '../api/analytics.api';

const COLOR_MAP: Record<string, string> = {
  excellent: Colors.excellent,
  good:      Colors.good,
  fair:      Colors.fair,
  poor:      Colors.poor,
  critical:  Colors.critical,
  none:      Colors.surfaceHigh,
};

const GRADE_LABELS: Record<string, string> = {
  excellent: 'Excellent',
  good:      'Good',
  fair:      'Fair',
  poor:      'Poor',
  critical:  'Critical',
  none:      'No data',
};

type DayEntry = {
  date: string;
  has_session: boolean;
  quality_score: number | null;
  grade: string | null;
  session_id: string | null;
  color: string;
  snoring_percentage: number | null;
  duration_minutes: number | null;
};

const DAYS_OPTIONS = [30, 90];
const WEEK_DAYS = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'];

type Props = NativeStackScreenProps<HistoryStackParams, 'Calendar'>;

export default function CalendarScreen({ navigation }: Props) {
  const [calendar,   setCalendar]   = useState<DayEntry[]>([]);
  const [days,       setDays]       = useState(90);
  const [loading,    setLoading]    = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [selected,   setSelected]   = useState<DayEntry | null>(null);
  const [loadError,  setLoadError]  = useState(false);
  const tooltipTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const load = useCallback(async (d = days) => {
    setLoadError(false);
    try {
      const res = await AnalyticsAPI.getCalendar(d);
      setCalendar(res.data.calendar ?? []);
    } catch { setLoadError(true); } finally { setLoading(false); setRefreshing(false); }
  }, [days]);

  // Auto-dismiss tooltip after 6 seconds
  useEffect(() => {
    if (!selected) return;
    tooltipTimer.current = setTimeout(() => setSelected(null), 6000);
    return () => { if (tooltipTimer.current) clearTimeout(tooltipTimer.current); };
  }, [selected]);

  useEffect(() => { load(); }, [load]);

  const handleDayPress = (entry: DayEntry) => {
    setSelected(entry);
  };

  const goToSession = () => {
    if (selected?.session_id) {
      navigation.navigate('SessionDetail', { sessionId: selected.session_id });
    }
    setSelected(null);
  };

  // Group into weeks starting from Sunday
  const buildGrid = () => {
    if (!calendar.length) return [];
    // Pad beginning to Sunday
    const firstDate  = new Date(calendar[0].date + 'T00:00:00Z');
    const startDay   = firstDate.getUTCDay(); // 0 = Sun
    const padded: (DayEntry | null)[] = Array(startDay).fill(null).concat(calendar as any[]);
    // Chunk into rows of 7
    const rows: (DayEntry | null)[][] = [];
    for (let i = 0; i < padded.length; i += 7) {
      rows.push(padded.slice(i, i + 7));
    }
    return rows;
  };

  const grid = buildGrid();
  const recorded = calendar.filter(d => d.has_session).length;
  const avgScore  = recorded
    ? Math.round(calendar.filter(d => d.quality_score != null).reduce((s, d) => s + (d.quality_score ?? 0), 0) / recorded)
    : 0;

  if (loading) return (
    <AuroraBackground style={styles.center}>
      <ActivityIndicator color={Colors.primary} size="large" />
    </AuroraBackground>
  );

  return (
    <AuroraBackground>
      <SafeAreaView style={{ flex: 1 }}>
      <ScrollView
        contentContainerStyle={styles.container}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} tintColor={Colors.primary} />}
      >
        <View style={styles.header}>
          <TouchableOpacity onPress={() => navigation.goBack()} accessibilityLabel="Go back">
            <Ionicons name="arrow-back" size={24} color={Colors.text} />
          </TouchableOpacity>
          <Text style={styles.title}>Sleep Calendar</Text>
          <View style={styles.periodRow}>
            {DAYS_OPTIONS.map(d => (
              <TouchableOpacity key={d} style={[styles.periodBtn, days === d && styles.periodBtnActive]} onPress={() => { setDays(d); load(d); }}>
                <Text style={[styles.periodBtnText, days === d && styles.periodBtnTextActive]}>{d}d</Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>

        {loadError && (
          <View style={styles.errorBanner}>
            <Ionicons name="cloud-offline-outline" size={16} color={Colors.danger} />
            <Text style={styles.errorBannerText}>Failed to load calendar. Pull down to retry.</Text>
          </View>
        )}

        {/* Summary */}
        <View style={styles.summaryRow}>
          <View style={styles.summaryItem}>
            <Text style={styles.summaryVal}>{recorded}</Text>
            <Text style={styles.summaryLbl}>nights recorded</Text>
          </View>
          <View style={styles.summaryItem}>
            <Text style={styles.summaryVal}>{avgScore || '—'}</Text>
            <Text style={styles.summaryLbl}>avg score</Text>
          </View>
          <View style={styles.summaryItem}>
            <Text style={styles.summaryVal}>{days - recorded}</Text>
            <Text style={styles.summaryLbl}>nights missed</Text>
          </View>
        </View>

        {/* Week day labels */}
        <View style={styles.weekRow}>
          {WEEK_DAYS.map(d => <Text key={d} style={styles.weekLabel}>{d}</Text>)}
        </View>

        {/* Calendar grid */}
        {grid.map((row, ri) => (
          <View key={ri} style={styles.calRow}>
            {row.map((entry, ci) =>
              entry ? (
                <TouchableOpacity
                  key={entry.date}
                  style={[styles.cell, { backgroundColor: COLOR_MAP[entry.color] ?? COLOR_MAP.none }]}
                  onPress={() => handleDayPress(entry)}
                  activeOpacity={entry.has_session ? 0.7 : 1}
                >
                  <Text style={styles.cellDay}>{new Date(entry.date + 'T00:00:00Z').getUTCDate()}</Text>
                </TouchableOpacity>
              ) : (
                <View key={`pad-${ri}-${ci}`} style={styles.cellEmpty} />
              )
            )}
          </View>
        ))}

        {/* Legend */}
        <View style={styles.legendRow}>
          {Object.entries(COLOR_MAP).map(([key, color]) => (
            <View key={key} style={styles.legendItem}>
              <View style={[styles.legendSwatch, { backgroundColor: color }]} />
              <Text style={styles.legendText}>{GRADE_LABELS[key]}</Text>
            </View>
          ))}
        </View>
      </ScrollView>

      {/* Day detail tooltip */}
      {selected && (
        <View style={styles.tooltip}>
          <View style={styles.tooltipContent}>
            <Text style={styles.tooltipDate}>{selected.date}</Text>
            {selected.has_session ? (
              <>
                <Text style={styles.tooltipScore}>Score: {selected.quality_score} ({selected.grade})</Text>
                <Text style={styles.tooltipSub}>Snoring: {selected.snoring_percentage}%  ·  {Math.floor((selected.duration_minutes ?? 0) / 60)}h {(selected.duration_minutes ?? 0) % 60}m</Text>
                <TouchableOpacity style={styles.tooltipBtn} onPress={goToSession}>
                  <Text style={styles.tooltipBtnText}>View Report</Text>
                </TouchableOpacity>
              </>
            ) : (
              <Text style={styles.tooltipSub}>No recording this night.</Text>
            )}
            <TouchableOpacity onPress={() => setSelected(null)} style={styles.tooltipClose}>
              <Ionicons name="close" size={18} color={Colors.textMuted} />
            </TouchableOpacity>
          </View>
        </View>
      )}
      </SafeAreaView>
    </AuroraBackground>
  );
}

const CELL_SIZE = 38;

const styles = StyleSheet.create({
  center:           { justifyContent: 'center', alignItems: 'center' },
  errorBanner:      { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: Colors.danger + '18', borderRadius: Radii.md, padding: 12, marginBottom: 16, borderWidth: 1, borderColor: Colors.danger + '33' },
  errorBannerText:  { color: Colors.danger, fontSize: 13, flex: 1 },
  container:        { padding: 20, paddingBottom: 60 },
  header:           { flexDirection: 'row', alignItems: 'center', marginBottom: 20, gap: 12 },
  title:            { color: Colors.text, fontSize: 20, fontWeight: '800', flex: 1, letterSpacing: -0.4 },
  periodRow:        { flexDirection: 'row', gap: 6, backgroundColor: 'rgba(31,31,61,0.6)', padding: 3, borderRadius: Radii.md, borderWidth: 1, borderColor: Colors.borderSoft },
  periodBtn:        { paddingHorizontal: 12, paddingVertical: 6, borderRadius: Radii.sm },
  periodBtnActive:  { backgroundColor: Colors.primary },
  periodBtnText:    { color: Colors.textSub, fontWeight: '700', fontSize: 12 },
  periodBtnTextActive: { color: '#fff' },
  summaryRow:       { flexDirection: 'row', justifyContent: 'space-around', backgroundColor: 'rgba(167,139,250,0.06)', borderRadius: Radii.xl, padding: 16, marginBottom: 20, borderWidth: 1, borderColor: Colors.borderSoft },
  summaryItem:      { alignItems: 'center', gap: 4 },
  summaryVal:       { color: Colors.text, fontSize: 22, fontWeight: '800' },
  summaryLbl:       { color: Colors.textMuted, fontSize: 11 },
  weekRow:          { flexDirection: 'row', marginBottom: 6, gap: 4 },
  weekLabel:        { width: CELL_SIZE, textAlign: 'center', color: Colors.textMuted, fontSize: 11, fontWeight: '600' },
  calRow:           { flexDirection: 'row', gap: 4, marginBottom: 4 },
  cell:             { width: CELL_SIZE, height: CELL_SIZE, borderRadius: 8, alignItems: 'center', justifyContent: 'center' },
  cellEmpty:        { width: CELL_SIZE, height: CELL_SIZE },
  cellDay:          { color: '#fff', fontSize: 11, fontWeight: '600', opacity: 0.9 },
  legendRow:        { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginTop: 20 },
  legendItem:       { flexDirection: 'row', alignItems: 'center', gap: 5 },
  legendSwatch:     { width: 12, height: 12, borderRadius: 3 },
  legendText:       { color: Colors.textMuted, fontSize: 11 },
  tooltip:          { position: 'absolute', bottom: 24, left: 16, right: 16 },
  tooltipContent:   { backgroundColor: Colors.surfaceHigh, borderRadius: Radii.xl, padding: 20, borderWidth: 1, borderColor: Colors.borderSoft, shadowColor: '#000', shadowOpacity: 0.4, shadowRadius: 14, shadowOffset: { width: 0, height: 8 }, elevation: 10 },
  tooltipDate:      { color: Colors.textMuted, fontSize: 11, marginBottom: 4, fontWeight: '600', letterSpacing: 0.6, textTransform: 'uppercase' },
  tooltipScore:     { color: Colors.text, fontWeight: '800', fontSize: 17, marginBottom: 4, letterSpacing: -0.4 },
  tooltipSub:       { color: Colors.textSub, fontSize: 13, fontWeight: '500' },
  tooltipBtn:       { marginTop: 12, backgroundColor: Colors.primary, borderRadius: Radii.md, padding: 10, alignItems: 'center' },
  tooltipBtnText:   { color: '#fff', fontWeight: '800', letterSpacing: 0.2 },
  tooltipClose:     { position: 'absolute', top: 12, right: 12 },
});
