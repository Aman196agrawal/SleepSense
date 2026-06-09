import React, { useMemo } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import Svg, { Circle, G } from 'react-native-svg';
import { Colors, Radii } from '../theme';

export const CLASS_COLORS: Record<string, string> = {
  snoring:   Colors.accent,      // pink
  breathing: Colors.secondary,   // sky-blue
  silence:   Colors.textMuted,
  ambient:   Colors.amber,
};

export const CLASS_LABELS: Record<string, string> = {
  snoring:   'Snoring',
  breathing: 'Breathing',
  silence:   'Silence',
  ambient:   'Ambient',
};

const ORDER = ['snoring', 'breathing', 'ambient', 'silence'] as const;

interface Bucket { dominant_class?: string | null }

interface Props {
  buckets: Bucket[];
  size?: number;
  /** Highlighted slice gets a small offset arc — currently unused, reserved for tap-to-highlight. */
  highlight?: string;
}

export default function ClassDonut({ buckets, size = 200 }: Props) {
  const stroke = Math.max(14, Math.round(size * 0.11));
  const r      = (size - stroke) / 2;
  const cx     = size / 2;
  const circ   = 2 * Math.PI * r;

  const { counts, total, dominant } = useMemo(() => {
    const counts: Record<string, number> = { snoring: 0, breathing: 0, silence: 0, ambient: 0 };
    for (const b of buckets) {
      const cls = b.dominant_class ?? 'silence';
      counts[cls] = (counts[cls] ?? 0) + 1;
    }
    const total = buckets.length || 1;
    let dominant = 'silence';
    let max = -1;
    for (const k of ORDER) {
      if (counts[k] > max) { max = counts[k]; dominant = k; }
    }
    return { counts, total, dominant };
  }, [buckets]);

  // Build arcs cumulatively — each circle starts at the previous arc's end
  let cumulative = 0;
  const arcs = ORDER.map(cls => {
    const frac = counts[cls] / total;
    const dash = frac * circ;
    const arc = {
      cls,
      dash,
      offset: -cumulative,
    };
    cumulative += dash;
    return arc;
  }).filter(a => a.dash > 0.5); // skip near-zero slices to avoid render artefacts

  const dominantPct = Math.round((counts[dominant] / total) * 100);

  return (
    <View style={styles.wrap}>
      <View style={{ width: size, height: size, alignItems: 'center', justifyContent: 'center' }}>
        <Svg width={size} height={size} style={StyleSheet.absoluteFill}>
          {/* Background ring */}
          <Circle cx={cx} cy={cx} r={r} stroke={Colors.surfaceHigh} strokeWidth={stroke} fill="none" />
          <G rotation={-90} origin={`${cx},${cx}`}>
            {arcs.map(a => (
              <Circle
                key={a.cls}
                cx={cx} cy={cx} r={r}
                stroke={CLASS_COLORS[a.cls]}
                strokeWidth={stroke}
                fill="none"
                strokeDasharray={`${a.dash} ${circ}`}
                strokeDashoffset={a.offset}
                strokeLinecap="butt"
              />
            ))}
          </G>
        </Svg>

        <View style={styles.centerLabel}>
          <Text style={[styles.percent, { color: CLASS_COLORS[dominant] }]}>{dominantPct}%</Text>
          <Text style={styles.dominantLabel}>{CLASS_LABELS[dominant]}</Text>
          <Text style={styles.totalLabel}>of the night</Text>
        </View>
      </View>

      {/* Legend */}
      <View style={styles.legend}>
        {ORDER.map(cls => {
          const pct = Math.round((counts[cls] / total) * 100);
          return (
            <View key={cls} style={styles.legendRow}>
              <View style={[styles.dot, { backgroundColor: CLASS_COLORS[cls] }]} />
              <Text style={styles.legendLabel}>{CLASS_LABELS[cls]}</Text>
              <Text style={styles.legendPct}>{pct}%</Text>
            </View>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 18,
  },
  centerLabel: { alignItems: 'center', justifyContent: 'center' },
  percent:     { fontSize: 32, fontWeight: '800', letterSpacing: -1 },
  dominantLabel: { color: Colors.text, fontSize: 13, fontWeight: '700', marginTop: 2, letterSpacing: -0.2 },
  totalLabel:  { color: Colors.textMuted, fontSize: 10, marginTop: 2, fontWeight: '600', letterSpacing: 0.4 },

  legend: { flex: 1, gap: 8 },
  legendRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  dot: { width: 10, height: 10, borderRadius: 3 },
  legendLabel: { flex: 1, color: Colors.textSub, fontSize: 13, fontWeight: '600' },
  legendPct: { color: Colors.text, fontSize: 13, fontWeight: '800', letterSpacing: -0.2, minWidth: 36, textAlign: 'right' },
});
