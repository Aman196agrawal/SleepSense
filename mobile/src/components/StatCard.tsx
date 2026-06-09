import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Radii } from '../theme';

interface Props { icon: string; label: string; value: string; color?: string; }

export default function StatCard({ icon, label, value, color = Colors.primary }: Props) {
  return (
    <View style={styles.card}>
      <View style={[styles.iconWrap, { backgroundColor: color + '22' }]}>
        <Ionicons name={icon as any} size={16} color={color} />
      </View>
      <Text style={styles.value}>{value}</Text>
      <Text style={styles.label}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card:     {
    flex: 1,
    backgroundColor: 'rgba(167,139,250,0.06)',
    borderRadius: Radii.lg,
    paddingVertical: 14,
    paddingHorizontal: 10,
    alignItems: 'center',
    gap: 6,
    borderWidth: 1,
    borderColor: Colors.borderSoft,
  },
  iconWrap: { width: 30, height: 30, borderRadius: Radii.sm, alignItems: 'center', justifyContent: 'center' },
  value:    { color: Colors.text, fontWeight: '800', fontSize: 17, letterSpacing: -0.4, marginTop: 2 },
  label:    { color: Colors.textMuted, fontSize: 11, textAlign: 'center', fontWeight: '600', letterSpacing: 0.3 },
});
