import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, ScrollView, StyleSheet, TouchableOpacity,
  Switch, ActivityIndicator, Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors } from '../theme/colors';
import * as AnalyticsAPI from '../api/analytics.api';

// ── helpers ──────────────────────────────────────────────────────────────────

const today = () => new Date().toISOString().slice(0, 10);
const yesterday = () => {
  const d = new Date();
  d.setDate(d.getDate() - 1);
  return d.toISOString().slice(0, 10);
};

const STRESS_LABELS = ['', 'Very Low', 'Low', 'Moderate', 'High', 'Very High'];
const STRESS_COLORS = ['', Colors.excellent, Colors.good, Colors.amber, Colors.poor, Colors.danger];

// ── stepper ───────────────────────────────────────────────────────────────────

function Stepper({
  value, min, max, step = 1, onChange, unit,
}: {
  value: number; min: number; max: number; step?: number;
  onChange: (v: number) => void; unit: string;
}) {
  return (
    <View style={step_s.row}>
      <TouchableOpacity
        style={[step_s.btn, value <= min && step_s.disabled]}
        onPress={() => onChange(Math.max(min, value - step))}
        disabled={value <= min}
      >
        <Ionicons name="remove" size={20} color={value <= min ? Colors.textMuted : Colors.text} />
      </TouchableOpacity>
      <View style={step_s.val}>
        <Text style={step_s.num}>{value}</Text>
        <Text style={step_s.unit}>{unit}</Text>
      </View>
      <TouchableOpacity
        style={[step_s.btn, value >= max && step_s.disabled]}
        onPress={() => onChange(Math.min(max, value + step))}
        disabled={value >= max}
      >
        <Ionicons name="add" size={20} color={value >= max ? Colors.textMuted : Colors.text} />
      </TouchableOpacity>
    </View>
  );
}

const step_s = StyleSheet.create({
  row:      { flexDirection: 'row', alignItems: 'center', gap: 12 },
  btn:      { width: 36, height: 36, borderRadius: 18, backgroundColor: Colors.surfaceHigh, alignItems: 'center', justifyContent: 'center' },
  disabled: { opacity: 0.4 },
  val:      { alignItems: 'center', minWidth: 56 },
  num:      { color: Colors.text, fontSize: 22, fontWeight: '800' },
  unit:     { color: Colors.textMuted, fontSize: 11, marginTop: 1 },
});

// ── stress selector ───────────────────────────────────────────────────────────

function StressSelector({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  return (
    <View style={{ flexDirection: 'row', gap: 8 }}>
      {[1, 2, 3, 4, 5].map(n => (
        <TouchableOpacity
          key={n}
          onPress={() => onChange(n)}
          style={[
            ss_s.dot,
            { borderColor: STRESS_COLORS[n], backgroundColor: value === n ? STRESS_COLORS[n] + '33' : 'transparent' },
          ]}
        >
          <Text style={[ss_s.label, { color: value === n ? STRESS_COLORS[n] : Colors.textMuted }]}>{n}</Text>
        </TouchableOpacity>
      ))}
    </View>
  );
}

const ss_s = StyleSheet.create({
  dot:   { flex: 1, paddingVertical: 8, borderRadius: 10, borderWidth: 1.5, alignItems: 'center' },
  label: { fontSize: 14, fontWeight: '700' },
});

// ── recent log row ────────────────────────────────────────────────────────────

function LogRow({ log }: { log: any }) {
  const icons: [string, string, any][] = [
    ['cafe-outline',     `${log.caffeine_cups} coffee`,    Colors.amber],
    ['wine-outline',     `${log.alcohol_units} alcohol`,   Colors.danger],
    ['barbell-outline',  `${log.exercise_minutes}m exercise`, Colors.secondary],
  ];
  return (
    <View style={lr_s.row}>
      <Text style={lr_s.date}>
        {new Date(log.logged_date + 'T12:00:00').toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })}
      </Text>
      <View style={lr_s.chips}>
        {icons.filter((_, i) => (i === 0 ? log.caffeine_cups > 0 : i === 1 ? log.alcohol_units > 0 : log.exercise_minutes > 0)).map(([icon, label, color]) => (
          <View key={icon} style={[lr_s.chip, { backgroundColor: color + '22' }]}>
            <Ionicons name={icon as any} size={12} color={color} />
            <Text style={[lr_s.chipText, { color }]}>{label}</Text>
          </View>
        ))}
        <View style={[lr_s.chip, { backgroundColor: STRESS_COLORS[log.stress_level] + '22' }]}>
          <Text style={[lr_s.chipText, { color: STRESS_COLORS[log.stress_level] }]}>
            stress {log.stress_level}
          </Text>
        </View>
      </View>
    </View>
  );
}

const lr_s = StyleSheet.create({
  row:      { flexDirection: 'row', alignItems: 'flex-start', gap: 10, paddingVertical: 10, borderBottomWidth: 1, borderColor: Colors.border },
  date:     { color: Colors.textSub, fontSize: 12, fontWeight: '600', width: 72, paddingTop: 2 },
  chips:    { flex: 1, flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  chip:     { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 8, paddingVertical: 3, borderRadius: 12 },
  chipText: { fontSize: 11, fontWeight: '600' },
});

// ── main screen ───────────────────────────────────────────────────────────────

export default function LifestyleLogScreen() {
  const [logDate,    setLogDate]    = useState(today());
  const [caffeine,   setCaffeine]   = useState(0);
  const [alcohol,    setAlcohol]    = useState(0);
  const [exercise,   setExercise]   = useState(0);
  const [stress,     setStress]     = useState(3);
  const [sleepAid,   setSleepAid]   = useState(false);
  const [saving,     setSaving]     = useState(false);
  const [recentLogs, setRecentLogs] = useState<any[]>([]);
  const [loadingLogs, setLoadingLogs] = useState(true);
  const [correlations, setCorrelations] = useState<any[]>([]);

  const loadLogs = useCallback(async () => {
    try {
      const [logsRes, corrRes] = await Promise.all([
        AnalyticsAPI.getLifestyleLogs(14),
        AnalyticsAPI.getLifestyleCorrelations(),
      ]);
      setRecentLogs(logsRes.data);
      setCorrelations(corrRes.data.correlations ?? []);
    } catch {}
    finally { setLoadingLogs(false); }
  }, []);

  useEffect(() => { loadLogs(); }, [loadLogs]);

  // Pre-fill if a log exists for selected date
  useEffect(() => {
    const existing = recentLogs.find(l => l.logged_date === logDate);
    if (existing) {
      setCaffeine(existing.caffeine_cups);
      setAlcohol(existing.alcohol_units);
      setExercise(existing.exercise_minutes);
      setStress(existing.stress_level);
      setSleepAid(existing.sleep_aid_used);
    } else {
      setCaffeine(0); setAlcohol(0); setExercise(0); setStress(3); setSleepAid(false);
    }
  }, [logDate, recentLogs]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await AnalyticsAPI.logLifestyle({
        logged_date: logDate,
        caffeine_cups: caffeine,
        alcohol_units: alcohol,
        exercise_minutes: exercise,
        stress_level: stress,
        sleep_aid_used: sleepAid,
      });
      await loadLogs();
      Alert.alert('Logged!', 'Your lifestyle factors have been saved.');
    } catch {
      Alert.alert('Error', 'Could not save. Is the analytics service running?');
    } finally {
      setSaving(false);
    }
  };

  const hasExisting = recentLogs.some(l => l.logged_date === logDate);

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.bg }}>
      <ScrollView contentContainerStyle={styles.container}>
        <Text style={styles.heading}>Lifestyle Log</Text>
        <Text style={styles.sub}>Track daily habits and see how they affect your sleep.</Text>

        {/* Date selector */}
        <View style={styles.dateRow}>
          {[today(), yesterday()].map(d => (
            <TouchableOpacity
              key={d}
              onPress={() => setLogDate(d)}
              style={[styles.dateBtn, logDate === d && styles.dateBtnActive]}
            >
              <Text style={[styles.dateBtnText, logDate === d && styles.dateBtnTextActive]}>
                {d === today() ? 'Today' : 'Yesterday'}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
        {hasExisting && (
          <Text style={styles.existingNote}>Editing existing log for this date</Text>
        )}

        {/* Log form */}
        <View style={styles.card}>
          <Row icon="cafe-outline" iconColor={Colors.amber} label="Caffeine">
            <Stepper value={caffeine} min={0} max={10} onChange={setCaffeine} unit="cups" />
          </Row>

          <Row icon="wine-outline" iconColor={Colors.danger} label="Alcohol">
            <Stepper value={alcohol} min={0} max={10} step={1} onChange={v => setAlcohol(v)} unit="units" />
          </Row>

          <Row icon="barbell-outline" iconColor={Colors.secondary} label="Exercise">
            <Stepper value={exercise} min={0} max={180} step={15} onChange={setExercise} unit="min" />
          </Row>

          <Row icon="brain-outline" iconColor={Colors.primary} label="Stress level">
            <View style={{ gap: 6 }}>
              <StressSelector value={stress} onChange={setStress} />
              <Text style={{ color: STRESS_COLORS[stress], fontSize: 12, fontWeight: '600', textAlign: 'center' }}>
                {STRESS_LABELS[stress]}
              </Text>
            </View>
          </Row>

          <View style={[styles.rowWrap, { paddingBottom: 0 }]}>
            <View style={styles.rowLeft}>
              <View style={[styles.iconBox, { backgroundColor: Colors.primary + '22' }]}>
                <Ionicons name="moon-outline" size={18} color={Colors.primary} />
              </View>
              <Text style={styles.rowLabel}>Sleep aid used</Text>
            </View>
            <Switch
              value={sleepAid}
              onValueChange={setSleepAid}
              trackColor={{ true: Colors.primary, false: Colors.border }}
              thumbColor="#fff"
            />
          </View>
        </View>

        <TouchableOpacity style={styles.saveBtn} onPress={handleSave} disabled={saving}>
          <Text style={styles.saveBtnText}>{saving ? 'Saving…' : hasExisting ? 'Update Log' : 'Save Log'}</Text>
        </TouchableOpacity>

        {/* Correlations */}
        {correlations.length > 0 && (
          <View style={{ marginTop: 24 }}>
            <Text style={styles.sectionTitle}>What your data shows</Text>
            {correlations.map((c, i) => (
              <View key={i} style={styles.corrCard}>
                <View style={[styles.corrIcon, {
                  backgroundColor: c.type === 'warning' ? Colors.danger + '22'
                                 : c.type === 'achievement' ? Colors.excellent + '22'
                                 : Colors.primary + '22'
                }]}>
                  <Ionicons
                    name={c.type === 'warning' ? 'warning-outline' : c.type === 'achievement' ? 'trophy-outline' : 'bulb-outline'}
                    size={18}
                    color={c.type === 'warning' ? Colors.danger : c.type === 'achievement' ? Colors.excellent : Colors.primary}
                  />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.corrTitle}>{c.title}</Text>
                  <Text style={styles.corrBody}>{c.body}</Text>
                </View>
              </View>
            ))}
          </View>
        )}

        {/* Recent logs */}
        {loadingLogs ? (
          <ActivityIndicator color={Colors.primary} style={{ marginTop: 32 }} />
        ) : recentLogs.length > 0 ? (
          <View style={{ marginTop: 24 }}>
            <Text style={styles.sectionTitle}>Recent Logs</Text>
            <View style={styles.logsCard}>
              {recentLogs.map(log => <LogRow key={log.id} log={log} />)}
            </View>
          </View>
        ) : null}
      </ScrollView>
    </SafeAreaView>
  );
}

function Row({ icon, iconColor, label, children }: {
  icon: string; iconColor: string; label: string; children: React.ReactNode;
}) {
  return (
    <View style={styles.rowWrap}>
      <View style={styles.rowLeft}>
        <View style={[styles.iconBox, { backgroundColor: iconColor + '22' }]}>
          <Ionicons name={icon as any} size={18} color={iconColor} />
        </View>
        <Text style={styles.rowLabel}>{label}</Text>
      </View>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  container:        { padding: 20, paddingBottom: 48 },
  heading:          { color: Colors.text, fontSize: 22, fontWeight: '700', marginBottom: 4 },
  sub:              { color: Colors.textSub, fontSize: 13, marginBottom: 20, lineHeight: 20 },
  dateRow:          { flexDirection: 'row', gap: 10, marginBottom: 8 },
  dateBtn:          { flex: 1, paddingVertical: 10, borderRadius: 12, borderWidth: 1, borderColor: Colors.border, alignItems: 'center' },
  dateBtnActive:    { backgroundColor: Colors.primary, borderColor: Colors.primary },
  dateBtnText:      { color: Colors.textSub, fontWeight: '600', fontSize: 14 },
  dateBtnTextActive:{ color: '#fff' },
  existingNote:     { color: Colors.primary, fontSize: 12, marginBottom: 12, textAlign: 'center' },
  card:             { backgroundColor: Colors.surface, borderRadius: 16, padding: 16, borderWidth: 1, borderColor: Colors.border, gap: 0 },
  rowWrap:          { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: 14, borderBottomWidth: 1, borderColor: Colors.border },
  rowLeft:          { flexDirection: 'row', alignItems: 'center', gap: 10 },
  iconBox:          { width: 34, height: 34, borderRadius: 8, alignItems: 'center', justifyContent: 'center' },
  rowLabel:         { color: Colors.text, fontSize: 14, fontWeight: '500' },
  saveBtn:          { backgroundColor: Colors.primary, borderRadius: 14, paddingVertical: 15, alignItems: 'center', marginTop: 20 },
  saveBtnText:      { color: '#fff', fontWeight: '700', fontSize: 16 },
  sectionTitle:     { color: Colors.text, fontWeight: '700', fontSize: 16, marginBottom: 12 },
  corrCard:         { flexDirection: 'row', gap: 12, backgroundColor: Colors.surface, borderRadius: 14, padding: 14, marginBottom: 10, borderWidth: 1, borderColor: Colors.border },
  corrIcon:         { width: 38, height: 38, borderRadius: 19, alignItems: 'center', justifyContent: 'center', flexShrink: 0 },
  corrTitle:        { color: Colors.text, fontWeight: '600', fontSize: 13, marginBottom: 3 },
  corrBody:         { color: Colors.textSub, fontSize: 12, lineHeight: 18 },
  logsCard:         { backgroundColor: Colors.surface, borderRadius: 14, paddingHorizontal: 14, borderWidth: 1, borderColor: Colors.border },
});
