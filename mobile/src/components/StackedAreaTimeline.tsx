import React, { useMemo } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import Svg, { Path, Defs, LinearGradient as SvgLinearGradient, Stop, Line } from 'react-native-svg';
import { Colors } from '../theme';
import { CLASS_COLORS, CLASS_LABELS } from './ClassDonut';

const ORDER = ['silence', 'breathing', 'ambient', 'snoring'] as const; // stack order (bottom → top)

interface Bucket {
  index?: number;
  offset_minutes?: number;
  dominant_class?: string | null;
}

interface Props {
  buckets: Bucket[];
  width?: number;
  height?: number;
  /** Rolling window in buckets — larger = smoother. ~5 min equivalent at 30s/bucket. */
  smoothing?: number;
}

const formatOffset = (min: number) => {
  const h = Math.floor(min / 60);
  const m = min % 60;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
};

export default function StackedAreaTimeline({
  buckets, width = 320, height = 140, smoothing = 10,
}: Props) {
  const padL = 8, padR = 8, padT = 14, padB = 22;
  const W = width  - padL - padR;
  const H = height - padT - padB;

  // For each bucket index, compute class proportions over a rolling window
  // centered on that bucket. With only `dominant_class` available per bucket,
  // smoothing is what makes a stacked area possible from winner-takes-all data.
  const series = useMemo(() => {
    if (!buckets.length) return null;
    const N = buckets.length;
    const half = Math.floor(smoothing / 2);
    const points: Record<string, number[]> = {
      snoring: [], breathing: [], silence: [], ambient: [],
    };
    for (let i = 0; i < N; i++) {
      const lo = Math.max(0, i - half);
      const hi = Math.min(N, i + half + 1);
      const window = buckets.slice(lo, hi);
      const counts: Record<string, number> = { snoring: 0, breathing: 0, silence: 0, ambient: 0 };
      for (const b of window) {
        const cls = b.dominant_class ?? 'silence';
        counts[cls] = (counts[cls] ?? 0) + 1;
      }
      const total = window.length || 1;
      for (const k of Object.keys(points)) {
        points[k].push(counts[k] / total);
      }
    }
    return points;
  }, [buckets, smoothing]);

  if (!series) return null;

  const N = buckets.length;
  const xAt = (i: number) => padL + (i / Math.max(N - 1, 1)) * W;
  const yAt = (frac: number) => padT + (1 - frac) * H;

  // Build stacked paths. Bottom layer (silence) first, then breathing, ambient, snoring on top.
  // Each layer's path covers [cumulativeBefore, cumulativeBefore + thisLayer].
  let cumulative = new Array(N).fill(0);
  const layers = ORDER.map(cls => {
    const top    = cumulative.map((v, i) => v + (series[cls][i] ?? 0));
    const bottom = [...cumulative];
    // Build SVG path: forward along top, back along bottom
    const fwd = top.map((v, i) => `${i === 0 ? 'M' : 'L'}${xAt(i).toFixed(2)},${yAt(v).toFixed(2)}`).join(' ');
    const back = bottom.slice().reverse().map((v, j) => {
      const i = N - 1 - j;
      return `L${xAt(i).toFixed(2)},${yAt(v).toFixed(2)}`;
    }).join(' ');
    cumulative = top;
    return { cls, d: `${fwd} ${back} Z` };
  });

  const startMin = buckets[0]?.offset_minutes ?? 0;
  const endMin   = buckets[N - 1]?.offset_minutes ?? 0;

  return (
    <View>
      <Svg width={width} height={height}>
        <Defs>
          {ORDER.map(cls => (
            <SvgLinearGradient key={cls} id={`grad-${cls}`} x1="0" y1="0" x2="0" y2="1">
              <Stop offset="0" stopColor={CLASS_COLORS[cls]} stopOpacity="0.85" />
              <Stop offset="1" stopColor={CLASS_COLORS[cls]} stopOpacity="0.55" />
            </SvgLinearGradient>
          ))}
        </Defs>

        {/* Grid lines at 25/50/75/100% */}
        {[0.25, 0.5, 0.75].map(f => (
          <Line
            key={f}
            x1={padL} x2={padL + W}
            y1={yAt(f)} y2={yAt(f)}
            stroke={Colors.borderSoft}
            strokeWidth={0.5}
          />
        ))}

        {layers.map(layer => (
          <Path
            key={layer.cls}
            d={layer.d}
            fill={`url(#grad-${layer.cls})`}
            stroke={CLASS_COLORS[layer.cls]}
            strokeWidth={0.5}
            strokeOpacity={0.4}
          />
        ))}
      </Svg>

      {/* X-axis labels */}
      <View style={[styles.axisRow, { paddingHorizontal: padL }]}>
        <Text style={styles.axisLabel}>{formatOffset(startMin)}</Text>
        <Text style={styles.axisLabel}>{formatOffset(endMin)}</Text>
      </View>

      {/* Legend */}
      <View style={styles.legend}>
        {(['snoring', 'breathing', 'ambient', 'silence'] as const).map(cls => (
          <View key={cls} style={styles.legendItem}>
            <View style={[styles.dot, { backgroundColor: CLASS_COLORS[cls] }]} />
            <Text style={styles.legendText}>{CLASS_LABELS[cls]}</Text>
          </View>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  axisRow: { flexDirection: 'row', justifyContent: 'space-between', marginTop: -16 },
  axisLabel: { color: Colors.textMuted, fontSize: 10, fontWeight: '600' },
  legend: { flexDirection: 'row', flexWrap: 'wrap', gap: 14, marginTop: 12 },
  legendItem: { flexDirection: 'row', alignItems: 'center', gap: 5 },
  dot: { width: 8, height: 8, borderRadius: 2 },
  legendText: { color: Colors.textSub, fontSize: 11, fontWeight: '600' },
});
