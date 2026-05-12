import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors } from '../theme/colors';

interface Props { title: string; body: string; type: string; onRead?: () => void; }

const typeConfig = {
  tip:         { icon: 'bulb-outline',      color: Colors.primary },
  warning:     { icon: 'warning-outline',   color: Colors.amber },
  achievement: { icon: 'trophy-outline',    color: Colors.excellent },
};

export default function InsightCard({ title, body, type, onRead }: Props) {
  const cfg = typeConfig[type as keyof typeof typeConfig] ?? typeConfig.tip;
  return (
    <View style={[styles.card, { borderLeftColor: cfg.color }]}>
      <View style={styles.row}>
        <View style={[styles.iconWrap, { backgroundColor: cfg.color + '22' }]}>
          <Ionicons name={cfg.icon as any} size={20} color={cfg.color} />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={styles.title}>{title}</Text>
          <Text style={styles.body}>{body}</Text>
        </View>
      </View>
      {onRead && (
        <TouchableOpacity onPress={onRead} style={styles.readBtn}>
          <Text style={[styles.readText, { color: cfg.color }]}>Got it ✓</Text>
        </TouchableOpacity>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  card:    { backgroundColor: Colors.surface, borderRadius: 14, padding: 16, borderLeftWidth: 3, marginBottom: 12 },
  row:     { flexDirection: 'row', gap: 12 },
  iconWrap:{ width: 40, height: 40, borderRadius: 20, alignItems: 'center', justifyContent: 'center', flexShrink: 0 },
  title:   { color: Colors.text, fontWeight: '600', fontSize: 14, marginBottom: 4 },
  body:    { color: Colors.textSub, fontSize: 13, lineHeight: 19 },
  readBtn: { alignSelf: 'flex-end', marginTop: 8 },
  readText:{ fontSize: 12, fontWeight: '600' },
});
