import React, { useEffect, useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, ScrollView,
  ActivityIndicator, Alert, RefreshControl, TextInput,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors } from '../theme/colors';
import * as AnalyticsAPI from '../api/analytics.api';

const GOAL_TYPES = [
  { key: 'quality_score',      label: 'Sleep Quality Score', icon: 'star-outline',    unit: 'pts', hint: 'Target 7-night avg (e.g. 80)' },
  { key: 'recording_streak',   label: 'Recording Streak',    icon: 'flame-outline',   unit: 'nights', hint: 'Consecutive nights (e.g. 7)' },
];

export default function GoalsScreen({ navigation }: any) {
  const [goals,      setGoals]      = useState<any[]>([]);
  const [loading,    setLoading]    = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [creating,   setCreating]   = useState(false);
  const [newType,    setNewType]    = useState<string | null>(null);
  const [targetVal,  setTargetVal]  = useState('');

  const load = useCallback(async () => {
    try {
      const res = await AnalyticsAPI.getGoals();
      setGoals(res.data);
    } catch {} finally { setLoading(false); setRefreshing(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleCreate = async () => {
    if (!newType || !targetVal) return;
    const tv = parseFloat(targetVal);
    if (isNaN(tv) || tv <= 0) { Alert.alert('Invalid', 'Enter a valid target number.'); return; }
    try {
      await AnalyticsAPI.createGoal({ goal_type: newType, target_value: tv });
      setCreating(false); setNewType(null); setTargetVal('');
      load();
    } catch (e: any) {
      Alert.alert('Error', e?.response?.data?.detail ?? 'Could not create goal.');
    }
  };

  const handleDelete = (id: string, label: string) => {
    Alert.alert('Delete Goal', `Remove "${label}"?`, [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Delete', style: 'destructive', onPress: async () => {
        try { await AnalyticsAPI.deleteGoal(id); load(); } catch {}
      }},
    ]);
  };

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
          <Text style={styles.title}>Sleep Goals</Text>
          <TouchableOpacity onPress={() => setCreating(!creating)}>
            <Ionicons name={creating ? 'close' : 'add-circle-outline'} size={26} color={Colors.primary} />
          </TouchableOpacity>
        </View>

        {/* Create form */}
        {creating && (
          <View style={styles.createCard}>
            <Text style={styles.createTitle}>New Goal</Text>
            {GOAL_TYPES.map(gt => (
              <TouchableOpacity
                key={gt.key}
                style={[styles.typeBtn, newType === gt.key && styles.typeBtnActive]}
                onPress={() => setNewType(gt.key)}
              >
                <Ionicons name={gt.icon as any} size={18} color={newType === gt.key ? Colors.bg : Colors.primary} />
                <Text style={[styles.typeBtnText, newType === gt.key && { color: Colors.bg }]}>{gt.label}</Text>
              </TouchableOpacity>
            ))}
            {newType && (
              <>
                <Text style={styles.createHint}>
                  {GOAL_TYPES.find(g => g.key === newType)?.hint}
                </Text>
                <TextInput
                  style={styles.input}
                  placeholder={`Target (${GOAL_TYPES.find(g => g.key === newType)?.unit})`}
                  placeholderTextColor={Colors.textMuted}
                  keyboardType="numeric"
                  value={targetVal}
                  onChangeText={setTargetVal}
                />
                <TouchableOpacity style={styles.saveBtn} onPress={handleCreate}>
                  <Text style={styles.saveBtnText}>Set Goal</Text>
                </TouchableOpacity>
              </>
            )}
          </View>
        )}

        {/* Active goals */}
        {goals.length === 0 && !creating ? (
          <View style={styles.empty}>
            <Ionicons name="flag-outline" size={52} color={Colors.textMuted} />
            <Text style={styles.emptyTitle}>No goals yet</Text>
            <Text style={styles.emptySub}>Tap + to set a sleep quality or recording streak goal.</Text>
          </View>
        ) : (
          goals.map(g => {
            const meta = GOAL_TYPES.find(gt => gt.key === g.goal_type);
            const pct = Math.min(g.progress_pct, 100);
            return (
              <View key={g.id} style={[styles.goalCard, g.is_achieved && styles.goalAchieved]}>
                <View style={styles.goalHeader}>
                  <View style={styles.goalLeft}>
                    <Ionicons name={(meta?.icon ?? 'flag-outline') as any} size={20} color={g.is_achieved ? Colors.excellent : Colors.primary} />
                    <Text style={styles.goalLabel}>{meta?.label ?? g.goal_type}</Text>
                    {g.is_achieved && <Text style={styles.achievedBadge}>Achieved!</Text>}
                  </View>
                  <TouchableOpacity onPress={() => handleDelete(g.id, meta?.label ?? g.goal_type)}>
                    <Ionicons name="trash-outline" size={18} color={Colors.textMuted} />
                  </TouchableOpacity>
                </View>
                <View style={styles.progressBg}>
                  <View style={[styles.progressFill, { width: `${pct}%`, backgroundColor: g.is_achieved ? Colors.excellent : Colors.primary }]} />
                </View>
                <Text style={styles.goalStat}>
                  {g.current_value} / {g.target_value} {meta?.unit} · {pct}% complete
                  {g.target_date ? `  ·  Due ${g.target_date}` : ''}
                </Text>
              </View>
            );
          })
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  center:        { flex: 1, backgroundColor: Colors.bg, justifyContent: 'center', alignItems: 'center' },
  container:     { padding: 20, paddingBottom: 40 },
  header:        { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 },
  title:         { color: Colors.text, fontSize: 20, fontWeight: '700' },
  createCard:    { backgroundColor: Colors.surface, borderRadius: 16, padding: 16, marginBottom: 20, borderWidth: 1, borderColor: Colors.primary + '55', gap: 10 },
  createTitle:   { color: Colors.text, fontWeight: '700', fontSize: 15, marginBottom: 4 },
  typeBtn:       { flexDirection: 'row', alignItems: 'center', gap: 10, padding: 12, borderRadius: 10, borderWidth: 1, borderColor: Colors.primary },
  typeBtnActive: { backgroundColor: Colors.primary },
  typeBtnText:   { color: Colors.primary, fontWeight: '600' },
  createHint:    { color: Colors.textMuted, fontSize: 12 },
  input:         { backgroundColor: Colors.surfaceHigh, borderRadius: 10, padding: 12, color: Colors.text, borderWidth: 1, borderColor: Colors.border },
  saveBtn:       { backgroundColor: Colors.primary, borderRadius: 10, padding: 14, alignItems: 'center' },
  saveBtnText:   { color: Colors.bg, fontWeight: '700', fontSize: 15 },
  empty:         { alignItems: 'center', paddingVertical: 60, gap: 12 },
  emptyTitle:    { color: Colors.text, fontWeight: '700', fontSize: 17 },
  emptySub:      { color: Colors.textMuted, textAlign: 'center', fontSize: 13, maxWidth: 260 },
  goalCard:      { backgroundColor: Colors.surface, borderRadius: 14, padding: 16, marginBottom: 12, borderWidth: 1, borderColor: Colors.border, gap: 10 },
  goalAchieved:  { borderColor: Colors.excellent + '55' },
  goalHeader:    { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  goalLeft:      { flexDirection: 'row', alignItems: 'center', gap: 8 },
  goalLabel:     { color: Colors.text, fontWeight: '600', fontSize: 14 },
  achievedBadge: { backgroundColor: Colors.excellent + '22', color: Colors.excellent, fontSize: 11, fontWeight: '700', paddingHorizontal: 8, paddingVertical: 2, borderRadius: 6 },
  progressBg:    { height: 8, backgroundColor: Colors.border, borderRadius: 4, overflow: 'hidden' },
  progressFill:  { height: '100%', borderRadius: 4 },
  goalStat:      { color: Colors.textMuted, fontSize: 12 },
});
