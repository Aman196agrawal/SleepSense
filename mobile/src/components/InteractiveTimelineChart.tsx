import React, { useMemo, useRef, useState } from 'react';
import { View, Text, ScrollView, StyleSheet, TouchableOpacity, NativeSyntheticEvent, NativeScrollEvent } from 'react-native';
import Svg, { Path, Line, Defs, LinearGradient, Stop, Text as SvgText } from 'react-native-svg';
import { Colors, Radii } from '../theme';

export interface TimelineBucket {
  index: number;
  offset_minutes: number;
  avg_intensity: number;
  dominant_class: string;
  snore_event_count: number;
}

interface Props {
  buckets: TimelineBucket[];
  /** ISO start time of the night — maps bucket offsets to clock time on the X axis. */
  startedAt?: string | null;
  width: number;
  height?: number;
}

const ZOOM_LEVELS = [1, 2, 4] as const;
const PAD_L = 30;   // Y-axis gutter (fixed overlay)
const PAD_R = 12;
const PAD_T = 14;
const PAD_B = 22;   // X-axis labels live inside the scroll content
const SMOOTH_WIN = 3;   // moving-average window (buckets) for the curve feel

/** Snap a raw max up to a "nice" round value so the auto Y-axis steps instead of
 *  jittering on every scroll frame. */
function niceMax(v: number): number {
  if (v <= 0) return 10;
  const step = v <= 20 ? 5 : v <= 50 ? 10 : 25;
  return Math.min(100, Math.ceil(v / step) * step);
}

function smooth(values: number[], win: number): number[] {
  if (win <= 1 || values.length < win) return values;
  const half = Math.floor(win / 2);
  return values.map((_, i) => {
    let sum = 0, n = 0;
    for (let j = i - half; j <= i + half; j++) {
      if (j >= 0 && j < values.length) { sum += values[j]; n++; }
    }
    return sum / n;
  });
}

function clockLabel(startedAt: string | null | undefined, offsetMin: number): string {
  if (!startedAt) {
    const h = Math.floor(offsetMin / 60), m = offsetMin % 60;
    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
  }
  const d = new Date(startedAt);
  d.setMinutes(d.getMinutes() + offsetMin);
  return d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', hour12: false });
}

export default function InteractiveTimelineChart({ buckets, startedAt, width, height = 200 }: Props) {
  const [zoom, setZoom] = useState<number>(1);
  const [scrollX, setScrollX] = useState(0);
  const scrollRef = useRef<ScrollView>(null);

  const plotW = width - PAD_L - PAD_R;
  const plotH = height - PAD_T - PAD_B;
  const contentW = plotW * zoom;

  // Smoothed intensity series (full night), memoised on the data only.
  const series = useMemo(
    () => smooth(buckets.map(b => b.avg_intensity), SMOOTH_WIN),
    [buckets],
  );
  const N = series.length;

  // Visible bucket window from the current horizontal scroll offset.
  const { visStart, visEnd } = useMemo(() => {
    if (N === 0 || zoom === 1) return { visStart: 0, visEnd: N };
    const frac = contentW > plotW ? scrollX / (contentW - plotW) : 0;
    const visibleCount = N / zoom;
    const start = Math.max(0, Math.floor(frac * (N - visibleCount)));
    return { visStart: start, visEnd: Math.min(N, Math.ceil(start + visibleCount)) };
  }, [scrollX, zoom, N, contentW, plotW]);

  // Auto Y-axis: scale to the loudest point in the *visible* window (snapped).
  const yMax = useMemo(() => {
    if (N === 0) return 100;
    let m = 0;
    for (let i = visStart; i < visEnd; i++) m = Math.max(m, series[i]);
    return niceMax(m);
  }, [series, visStart, visEnd, N]);

  // Build the area + line paths across the full content width.
  const { areaPath, linePath } = useMemo(() => {
    if (N === 0) return { areaPath: '', linePath: '' };
    const toX = (i: number) => (N === 1 ? 0 : (i / (N - 1)) * contentW);
    const toY = (v: number) => plotH - (Math.min(v, yMax) / yMax) * plotH;
    let line = '';
    for (let i = 0; i < N; i++) line += `${i === 0 ? 'M' : 'L'}${toX(i).toFixed(1)},${(toY(series[i]) + PAD_T).toFixed(1)} `;
    const area = `M0,${(plotH + PAD_T).toFixed(1)} ` +
      series.map((v, i) => `L${toX(i).toFixed(1)},${(toY(v) + PAD_T).toFixed(1)}`).join(' ') +
      ` L${contentW.toFixed(1)},${(plotH + PAD_T).toFixed(1)} Z`;
    return { areaPath: area, linePath: line };
  }, [series, N, contentW, plotH, yMax]);

  // X-axis time ticks (4 across the visible night), positioned in content space.
  const ticks = useMemo(() => {
    if (N === 0) return [];
    const count = 4;
    return Array.from({ length: count + 1 }, (_, k) => {
      const i = Math.round((k / count) * (N - 1));
      return { x: (N === 1 ? 0 : (i / (N - 1)) * contentW), label: clockLabel(startedAt, buckets[i]?.offset_minutes ?? 0) };
    });
  }, [N, contentW, startedAt, buckets]);

  const onScroll = (e: NativeSyntheticEvent<NativeScrollEvent>) => setScrollX(e.nativeEvent.contentOffset.x);

  const changeZoom = (z: number) => {
    // Keep the current view centred when zoom changes.
    const centerFrac = contentW > plotW ? (scrollX + plotW / 2) / contentW : 0.5;
    setZoom(z);
    requestAnimationFrame(() => {
      const newContentW = plotW * z;
      const target = Math.max(0, Math.min(newContentW - plotW, centerFrac * newContentW - plotW / 2));
      scrollRef.current?.scrollTo({ x: target, animated: false });
      setScrollX(target);
    });
  };

  if (N === 0) {
    return <View style={[styles.empty, { width, height }]}><Text style={styles.emptyText}>No timeline data</Text></View>;
  }

  const gridYs = [0, 0.5, 1];

  return (
    <View style={{ width }}>
      {/* Zoom controls */}
      <View style={styles.zoomRow}>
        {ZOOM_LEVELS.map(z => (
          <TouchableOpacity
            key={z}
            onPress={() => changeZoom(z)}
            style={[styles.zoomBtn, zoom === z && styles.zoomBtnActive]}
            accessibilityLabel={`Zoom ${z}x`}
          >
            <Text style={[styles.zoomText, zoom === z && { color: Colors.bg }]}>{z}×</Text>
          </TouchableOpacity>
        ))}
      </View>

      <View style={{ width, height }}>
        {/* Fixed Y-axis overlay (auto-rescaling labels) */}
        <View style={styles.yAxis} pointerEvents="none">
          <Text style={styles.yLabel}>{yMax}</Text>
          <Text style={styles.yLabel}>{Math.round(yMax / 2)}</Text>
          <Text style={[styles.yLabel, { marginBottom: PAD_B - 6 }]}>0</Text>
        </View>

        {/* Scrollable plot area (native horizontal pan; disabled when it all fits) */}
        <ScrollView
          ref={scrollRef}
          horizontal
          scrollEnabled={zoom > 1}
          showsHorizontalScrollIndicator={false}
          scrollEventThrottle={16}
          onScroll={onScroll}
          style={{ marginLeft: PAD_L }}
          contentContainerStyle={{ width: contentW + PAD_R }}
        >
          <Svg width={contentW + PAD_R} height={height}>
            <Defs>
              <LinearGradient id="fill" x1="0" y1="0" x2="0" y2="1">
                <Stop offset="0" stopColor={Colors.accent} stopOpacity={0.45} />
                <Stop offset="1" stopColor={Colors.accent} stopOpacity={0.02} />
              </LinearGradient>
            </Defs>

            {/* Gridlines */}
            {gridYs.map(g => (
              <Line
                key={g}
                x1={0} x2={contentW}
                y1={PAD_T + g * plotH} y2={PAD_T + g * plotH}
                stroke={Colors.border} strokeWidth={0.5} strokeDasharray={g === 1 ? undefined : '3,4'}
              />
            ))}

            {/* Curve */}
            <Path d={areaPath} fill="url(#fill)" />
            <Path d={linePath} fill="none" stroke={Colors.accent} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />

            {/* X-axis time labels */}
            {ticks.map((t, k) => (
              <SvgText
                key={k}
                x={Math.max(8, Math.min(contentW - 8, t.x))}
                y={height - 6}
                fill={Colors.textMuted}
                fontSize={9}
                textAnchor={k === 0 ? 'start' : k === ticks.length - 1 ? 'end' : 'middle'}
              >
                {t.label}
              </SvgText>
            ))}
          </Svg>
        </ScrollView>
      </View>

      <Text style={styles.hint}>
        {zoom === 1 ? 'Pinch-free: tap 2× / 4× to zoom, then drag to scan the night' : 'Drag to scan · axis auto-scales to the visible window'}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  zoomRow:      { flexDirection: 'row', alignSelf: 'flex-end', gap: 4, marginBottom: 8, backgroundColor: 'rgba(31,31,61,0.6)', padding: 3, borderRadius: Radii.md, borderWidth: 1, borderColor: Colors.borderSoft },
  zoomBtn:      { paddingHorizontal: 12, paddingVertical: 5, borderRadius: Radii.sm },
  zoomBtnActive:{ backgroundColor: Colors.accent },
  zoomText:     { color: Colors.textSub, fontWeight: '700', fontSize: 12, letterSpacing: 0.2 },
  yAxis:        { position: 'absolute', left: 0, top: PAD_T - 6, bottom: 0, width: PAD_L - 4, justifyContent: 'space-between', alignItems: 'flex-end' },
  yLabel:       { color: Colors.textMuted, fontSize: 9, fontWeight: '600' },
  empty:        { alignItems: 'center', justifyContent: 'center' },
  emptyText:    { color: Colors.textMuted, fontSize: 13 },
  hint:         { color: Colors.textMuted, fontSize: 10, marginTop: 6, textAlign: 'center', fontWeight: '500' },
});
