import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors } from '../theme/colors';

interface Props { icon: string; label: string; value: string; color?: string; }

export default function StatCard({ icon, label, value, color = Colors.primary }: Props) {
  return (
    <View style={styles.card}>
      <Ionicons name={icon as any} size={20} color={color} />
      <Text style={styles.value}>{value}</Text>
      <Text style={styles.label}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card:  { flex: 1, backgroundColor: Colors.surface, borderRadius: 14, padding: 14, alignItems: 'center', gap: 6, borderWidth: 1, borderColor: Colors.border },
  value: { color: Colors.text, fontWeight: '800', fontSize: 18 },
  label: { color: Colors.textMuted, fontSize: 11, textAlign: 'center' },
});
