import React from 'react';
import { View, Text } from 'react-native';
import Svg, { Circle } from 'react-native-svg';
import { scoreColor } from '../theme/colors';

interface Props { score: number; size?: number; grade?: string; }

export default function ScoreRing({ score, size = 160, grade }: Props) {
  const stroke   = 10;
  const r        = (size - stroke) / 2;
  const cx       = size / 2;
  const circumf  = 2 * Math.PI * r;
  const progress = Math.max(0, Math.min(score / 100, 1));
  const dash     = progress * circumf;
  const color    = scoreColor(score);

  return (
    <View style={{ alignItems: 'center', justifyContent: 'center', width: size, height: size }}>
      <Svg width={size} height={size} style={{ position: 'absolute' }}>
        <Circle cx={cx} cy={cx} r={r} stroke="#1E3A5F" strokeWidth={stroke} fill="none" />
        <Circle
          cx={cx} cy={cx} r={r}
          stroke={color} strokeWidth={stroke} fill="none"
          strokeDasharray={`${dash} ${circumf}`}
          strokeLinecap="round"
          rotation="-90" origin={`${cx},${cx}`}
        />
      </Svg>
      <Text style={{ fontSize: size * 0.28, fontWeight: '800', color, lineHeight: size * 0.32 }}>
        {Math.round(score)}
      </Text>
      {grade && (
        <Text style={{ fontSize: size * 0.1, color, fontWeight: '600', marginTop: 2 }}>{grade}</Text>
      )}
    </View>
  );
}
