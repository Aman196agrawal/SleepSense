import React from 'react';
import { View, Text, ScrollView } from 'react-native';
import Svg, { Rect } from 'react-native-svg';
import { Colors } from '../theme/colors';

interface Bucket { index: number; offset_minutes: number; avg_intensity: number; dominant_class: string; }
interface Props  { buckets: Bucket[]; height?: number; }

const classColor = (cls: string) => {
  if (cls === 'snoring')   return '#F43F5E';
  if (cls === 'breathing') return '#3D8EF0';
  if (cls === 'ambient')   return '#F59E0B';
  return '#1E3A5F';
};

export default function TimelineChart({ buckets, height = 100 }: Props) {
  if (!buckets.length) return null;
  const barW = 6;
  const gap  = 2;
  const totalW = buckets.length * (barW + gap);

  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false}>
      <View>
        <Svg width={totalW} height={height}>
          {buckets.map((b, i) => {
            const barH = Math.max(3, (b.avg_intensity / 100) * (height - 20));
            return (
              <Rect
                key={i}
                x={i * (barW + gap)}
                y={height - barH - 16}
                width={barW}
                height={barH}
                rx={2}
                fill={classColor(b.dominant_class)}
                opacity={0.85}
              />
            );
          })}
        </Svg>
        <View style={{ flexDirection: 'row', justifyContent: 'space-between', paddingHorizontal: 2 }}>
          <Text style={{ color: Colors.textMuted, fontSize: 10 }}>
            {buckets[0] ? formatOffset(buckets[0].offset_minutes) : ''}
          </Text>
          <Text style={{ color: Colors.textMuted, fontSize: 10 }}>
            {buckets[buckets.length - 1] ? formatOffset(buckets[buckets.length - 1].offset_minutes) : ''}
          </Text>
        </View>
      </View>
    </ScrollView>
  );
}

function formatOffset(minutes: number) {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
}
