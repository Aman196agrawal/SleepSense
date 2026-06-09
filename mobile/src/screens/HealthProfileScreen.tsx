import React, { useState, useEffect } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  ScrollView, Switch, Alert, ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { Colors } from '../theme';
import type { ProfileStackParams } from '../navigation/MainNavigator';
import * as AuthAPI from '../api/auth.api';

type Option = { label: string; value: string };

const SLEEP_POSITIONS: Option[] = [
  { label: 'Back',    value: 'back' },
  { label: 'Side',    value: 'side' },
  { label: 'Stomach', value: 'stomach' },
];
const ALCOHOL_OPTS: Option[] = [
  { label: 'Never',        value: 'never' },
  { label: 'Occasionally', value: 'occasionally' },
  { label: 'Regularly',    value: 'regularly' },
];
const SMOKING_OPTS: Option[] = [
  { label: 'Never',  value: 'never' },
  { label: 'Former', value: 'former' },
  { label: 'Current',value: 'current' },
];

function SegmentedPicker({ options, value, onChange }: { options: Option[]; value: string | null; onChange: (v: string) => void }) {
  return (
    <View style={seg.row}>
      {options.map(o => (
        <TouchableOpacity
          key={o.value}
          style={[seg.btn, value === o.value && seg.active]}
          onPress={() => onChange(o.value)}
        >
          <Text style={[seg.label, value === o.value && seg.activeLabel]}>{o.label}</Text>
        </TouchableOpacity>
      ))}
    </View>
  );
}

const seg = StyleSheet.create({
  row:         { flexDirection: 'row', gap: 8 },
  btn:         { flex: 1, paddingVertical: 10, borderRadius: 10, borderWidth: 1, borderColor: Colors.border, alignItems: 'center' },
  active:      { backgroundColor: Colors.primary + '22', borderColor: Colors.primary },
  label:       { color: Colors.textSub, fontSize: 13, fontWeight: '500' },
  activeLabel: { color: Colors.primary, fontWeight: '700' },
});

function SeverityPicker({ value, onChange }: { value: number | null; onChange: (v: number) => void }) {
  return (
    <View style={{ flexDirection: 'row', gap: 8 }}>
      {[1, 2, 3, 4, 5].map(n => (
        <TouchableOpacity
          key={n}
          style={[sev.btn, value === n && sev.active]}
          onPress={() => onChange(n)}
        >
          <Text style={[sev.label, value === n && sev.activeLabel]}>{n}</Text>
        </TouchableOpacity>
      ))}
    </View>
  );
}
const sev = StyleSheet.create({
  btn:         { flex: 1, paddingVertical: 12, borderRadius: 10, borderWidth: 1, borderColor: Colors.border, alignItems: 'center' },
  active:      { backgroundColor: Colors.primary, borderColor: Colors.primary },
  label:       { color: Colors.textSub, fontSize: 15, fontWeight: '600' },
  activeLabel: { color: '#fff' },
});

function TagInput({ tags, onChange, placeholder }: { tags: string[]; onChange: (t: string[]) => void; placeholder: string }) {
  const [input, setInput] = useState('');
  const add = () => {
    const v = input.trim();
    if (v && !tags.includes(v)) onChange([...tags, v]);
    setInput('');
  };
  return (
    <View>
      <View style={tag.row}>
        <TextInput
          style={tag.input}
          value={input}
          onChangeText={setInput}
          placeholder={placeholder}
          placeholderTextColor={Colors.textMuted}
          onSubmitEditing={add}
          returnKeyType="done"
        />
        <TouchableOpacity style={tag.addBtn} onPress={add}>
          <Ionicons name="add" size={20} color={Colors.primary} />
        </TouchableOpacity>
      </View>
      {tags.length > 0 && (
        <View style={tag.wrap}>
          {tags.map(t => (
            <View key={t} style={tag.chip}>
              <Text style={tag.chipText}>{t}</Text>
              <TouchableOpacity onPress={() => onChange(tags.filter(x => x !== t))}>
                <Ionicons name="close-circle" size={16} color={Colors.textMuted} />
              </TouchableOpacity>
            </View>
          ))}
        </View>
      )}
    </View>
  );
}
const tag = StyleSheet.create({
  row:      { flexDirection: 'row', alignItems: 'center', backgroundColor: Colors.bg, borderRadius: 12, borderWidth: 1, borderColor: Colors.border, paddingLeft: 14, paddingRight: 6, paddingVertical: 6 },
  input:    { flex: 1, color: Colors.text, fontSize: 14, paddingVertical: 6 },
  addBtn:   { padding: 6 },
  wrap:     { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 10 },
  chip:     { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: Colors.surfaceHigh, borderRadius: 20, paddingHorizontal: 12, paddingVertical: 6 },
  chipText: { color: Colors.text, fontSize: 13 },
});

type Props = NativeStackScreenProps<ProfileStackParams, 'HealthProfile'>;

export default function HealthProfileScreen({ navigation }: Props) {
  const [loading, setLoading]     = useState(true);
  const [saving, setSaving]       = useState(false);
  const [sleepPos, setSleepPos]   = useState<string | null>(null);
  const [conditions, setConditions] = useState<string[]>([]);
  const [medications, setMedications] = useState<string[]>([]);
  const [alcohol, setAlcohol]     = useState<string | null>(null);
  const [smoking, setSmoking]     = useState<string | null>(null);
  const [cpap, setCpap]           = useState(false);
  const [severity, setSeverity]   = useState<number | null>(null);

  useEffect(() => {
    AuthAPI.getHealthProfile()
      .then(r => {
        const d = r.data;
        if (d.sleep_position)        setSleepPos(d.sleep_position);
        if (d.known_conditions)      setConditions(d.known_conditions);
        if (d.medications)           setMedications(d.medications);
        if (d.alcohol_frequency)     setAlcohol(d.alcohol_frequency);
        if (d.smoking_status)        setSmoking(d.smoking_status);
        if (d.cpap_user != null)     setCpap(d.cpap_user);
        if (d.snoring_severity_self) setSeverity(d.snoring_severity_self);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      await AuthAPI.putHealthProfile({
        ...(sleepPos   && { sleep_position: sleepPos }),
        ...(conditions.length && { known_conditions: conditions }),
        ...(medications.length && { medications }),
        ...(alcohol    && { alcohol_frequency: alcohol }),
        ...(smoking    && { smoking_status: smoking }),
        cpap_user: cpap,
        ...(severity   && { snoring_severity_self: severity }),
      });
      Alert.alert('Saved', 'Health profile updated successfully.');
    } catch {
      Alert.alert('Error', 'Could not save profile. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <SafeAreaView style={{ flex: 1, backgroundColor: Colors.bg, justifyContent: 'center', alignItems: 'center' }}>
        <ActivityIndicator color={Colors.primary} size="large" />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.bg }}>
      <ScrollView contentContainerStyle={styles.container}>

        {/* Header */}
        <View style={styles.header}>
          <TouchableOpacity onPress={() => navigation.goBack()}>
            <Ionicons name="arrow-back" size={24} color={Colors.text} />
          </TouchableOpacity>
          <Text style={styles.heading}>Health Profile</Text>
          <TouchableOpacity onPress={handleSave} disabled={saving}>
            <Text style={[styles.saveBtn, saving && { opacity: 0.5 }]}>{saving ? 'Saving…' : 'Save'}</Text>
          </TouchableOpacity>
        </View>

        <Text style={styles.sub}>This information helps personalise your sleep recommendations.</Text>

        {/* Sleep Position */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Sleep Position</Text>
          <View style={styles.card}>
            <SegmentedPicker options={SLEEP_POSITIONS} value={sleepPos} onChange={setSleepPos} />
          </View>
        </View>

        {/* Snoring Severity */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Self-Rated Snoring Severity</Text>
          <Text style={styles.hint}>1 = Barely snore &nbsp;·&nbsp; 5 = Very loud / stop breathing</Text>
          <View style={styles.card}>
            <SeverityPicker value={severity} onChange={setSeverity} />
          </View>
        </View>

        {/* CPAP */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>CPAP / Sleep Device</Text>
          <View style={[styles.card, styles.row]}>
            <View style={{ flex: 1 }}>
              <Text style={styles.rowLabel}>I use a CPAP or similar device</Text>
              <Text style={styles.rowSub}>Helps calibrate intensity thresholds</Text>
            </View>
            <Switch
              value={cpap}
              onValueChange={setCpap}
              trackColor={{ false: Colors.border, true: Colors.primary + '88' }}
              thumbColor={cpap ? Colors.primary : Colors.textMuted}
            />
          </View>
        </View>

        {/* Alcohol */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Alcohol Consumption</Text>
          <View style={styles.card}>
            <SegmentedPicker options={ALCOHOL_OPTS} value={alcohol} onChange={setAlcohol} />
          </View>
        </View>

        {/* Smoking */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Smoking Status</Text>
          <View style={styles.card}>
            <SegmentedPicker options={SMOKING_OPTS} value={smoking} onChange={setSmoking} />
          </View>
        </View>

        {/* Known Conditions */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Known Conditions</Text>
          <Text style={styles.hint}>e.g. asthma, obesity, sleep apnea</Text>
          <View style={styles.card}>
            <TagInput tags={conditions} onChange={setConditions} placeholder="Type and press Enter…" />
          </View>
        </View>

        {/* Medications */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Medications</Text>
          <Text style={styles.hint}>e.g. antihistamines, sedatives</Text>
          <View style={styles.card}>
            <TagInput tags={medications} onChange={setMedications} placeholder="Type and press Enter…" />
          </View>
        </View>

        <TouchableOpacity style={styles.saveFullBtn} onPress={handleSave} disabled={saving}>
          <Text style={styles.saveFullText}>{saving ? 'Saving…' : 'Save Health Profile'}</Text>
        </TouchableOpacity>

      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container:    { padding: 20, paddingBottom: 40 },
  header:       { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 },
  heading:      { color: Colors.text, fontSize: 20, fontWeight: '700' },
  saveBtn:      { color: Colors.primary, fontSize: 16, fontWeight: '700' },
  sub:          { color: Colors.textSub, fontSize: 13, marginBottom: 24, lineHeight: 18 },
  section:      { marginBottom: 20 },
  sectionTitle: { color: Colors.textMuted, fontSize: 12, fontWeight: '600', letterSpacing: 0.8, textTransform: 'uppercase', marginBottom: 6, marginLeft: 2 },
  hint:         { color: Colors.textMuted, fontSize: 12, marginBottom: 8, marginLeft: 2 },
  card:         { backgroundColor: Colors.surface, borderRadius: 14, padding: 16, borderWidth: 1, borderColor: Colors.border },
  row:          { flexDirection: 'row', alignItems: 'center' },
  rowLabel:     { color: Colors.text, fontSize: 14, fontWeight: '500' },
  rowSub:       { color: Colors.textMuted, fontSize: 12, marginTop: 2 },
  saveFullBtn:  { backgroundColor: Colors.primary, borderRadius: 14, paddingVertical: 16, alignItems: 'center', marginTop: 8 },
  saveFullText: { color: '#fff', fontSize: 16, fontWeight: '700' },
});
