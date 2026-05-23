import React, { useCallback, useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  ActivityIndicator, RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors } from '../theme/colors';
import * as AnalyticsAPI from '../api/analytics.api';

const COLOR_MAP: Record<string, string> = {
  excellent: Colors.excellent ?? '#22C55E',
  good:      '#4ADE80',
  fair:      '#FACC15',
  poor:      '#F97316',
  critical:  '#EF4444',
  none:      Colors.surfaceHigh ?? '#1A2E4A',
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

export default function CalendarScreen({ navigation }: any) {
  const [calendar,   setCalendar]   = useState<DayEntry[]>([]);
  const [days,       setDays]       = useState(90);
  const [loading,    setLoading]    = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [selected,   setSelected]   = useState<DayEntry | null>(null);

  const load = useCallback(async (d = days) => {
    try {
      const res = await AnalyticsAPI.getCalendar(d);
      setCalendar(res.data.calendar ?? []);
    } catch {} finally { setLoading(false); setRefreshing(false); }
  }, [days]);

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

  if (loading) return <View style={styles.center}><ActivityIndicator color={Colors.primary} size="large" /></View>;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.bg }}>
      <ScrollView
        contentContainerStyle={styles.container}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} tintColor={Colors.primary} />}
      >
        <View style={styles.header}>
          <TouchableOpacity onPress={() => navigation.goBack()}>
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
  );
}

const CELL_SIZE = 38;

const styles = StyleSheet.create({
  center:           { flex: 1, backgroundColor: Colors.bg, justifyContent: 'center', alignItems: 'center' },
  container:        { padding: 20, paddingBottom: 60 },
  header:           { flexDirection: 'row', alignItems: 'center', marginBottom: 20, gap: 12 },
  title:            { color: Colors.text, fontSize: 18, fontWeight: '700', flex: 1 },
  periodRow:        { flexDirection: 'row', gap: 8 },
  periodBtn:        { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 8, borderWidth: 1, borderColor: Colors.primary },
  periodBtnActive:  { backgroundColor: Colors.primary },
  periodBtnText:    { color: Colors.primary, fontWeight: '600', fontSize: 12 },
  periodBtnTextActive: { color: Colors.bg },
  summaryRow:       { flexDirection: 'row', justifyContent: 'space-around', backgroundColor: Colors.surface, borderRadius: 14, padding: 16, marginBottom: 20 },
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
  tooltipContent:   { backgroundColor: Colors.surface, borderRadius: 16, padding: 20, borderWidth: 1, borderColor: Colors.border },
  tooltipDate:      { color: Colors.textMuted, fontSize: 12, marginBottom: 4 },
  tooltipScore:     { color: Colors.text, fontWeight: '700', fontSize: 16, marginBottom: 4 },
  tooltipSub:       { color: Colors.textSub, fontSize: 13 },
  tooltipBtn:       { marginTop: 12, backgroundColor: Colors.primary, borderRadius: 10, padding: 10, alignItems: 'center' },
  tooltipBtnText:   { color: Colors.bg, fontWeight: '700' },
  tooltipClose:     { position: 'absolute', top: 12, right: 12 },
});
