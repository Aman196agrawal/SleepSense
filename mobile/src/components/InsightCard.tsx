import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { Colors, Radii } from '../theme';

interface Props { title: string; body: string; type: string; onRead?: () => void; }

const typeConfig: Record<string, { icon: keyof typeof Ionicons.glyphMap; color: string }> = {
  tip:         { icon: 'bulb-outline',    color: Colors.primary },
  warning:     { icon: 'alert-outline',   color: Colors.amber },
  achievement: { icon: 'trophy-outline',  color: Colors.excellent },
};

export default function InsightCard({ title, body, type, onRead }: Props) {
  const cfg = typeConfig[type] ?? typeConfig.tip;
  return (
    <View style={styles.outer}>
      <LinearGradient
        colors={[cfg.color + '18', 'rgba(31,31,61,0.6)']}
        start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
        style={styles.card}
      >
        <View style={[styles.accentBar, { backgroundColor: cfg.color }]} />
        <View style={styles.row}>
          <View style={[styles.iconWrap, { backgroundColor: cfg.color + '26' }]}>
            <Ionicons name={cfg.icon} size={20} color={cfg.color} />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.title}>{title}</Text>
            <Text style={styles.body}>{body}</Text>
          </View>
        </View>
        {onRead && (
          <TouchableOpacity onPress={onRead} style={styles.readBtn}>
            <Text style={[styles.readText, { color: cfg.color }]}>Got it</Text>
            <Ionicons name="checkmark" size={13} color={cfg.color} />
          </TouchableOpacity>
        )}
      </LinearGradient>
    </View>
  );
}

const styles = StyleSheet.create({
  outer:    { borderRadius: Radii.lg, marginBottom: 12, overflow: 'hidden' },
  card:     { padding: 16, paddingLeft: 18, borderWidth: 1, borderColor: Colors.borderSoft, borderRadius: Radii.lg },
  accentBar:{ position: 'absolute', left: 0, top: 12, bottom: 12, width: 3, borderTopRightRadius: 4, borderBottomRightRadius: 4 },
  row:      { flexDirection: 'row', gap: 12, alignItems: 'flex-start' },
  iconWrap: { width: 38, height: 38, borderRadius: Radii.md, alignItems: 'center', justifyContent: 'center', flexShrink: 0 },
  title:    { color: Colors.text, fontWeight: '700', fontSize: 14, marginBottom: 4, letterSpacing: -0.2 },
  body:     { color: Colors.textSub, fontSize: 13, lineHeight: 20 },
  readBtn:  { alignSelf: 'flex-end', flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 10 },
  readText: { fontSize: 12, fontWeight: '700' },
});
