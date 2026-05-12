import React from 'react';
import { View, Text } from 'react-native';
import Svg, { Polyline, Line, Circle, Text as SvgText } from 'react-native-svg';
import { Colors, scoreColor } from '../theme/colors';

interface Point { date: string; quality_score: number; }
interface Props  { data: Point[]; width?: number; height?: number; }

export default function TrendChart({ data, width = 320, height = 140 }: Props) {
  if (!data.length) return null;

  const padL = 28, padR = 12, padT = 12, padB = 28;
  const W = width - padL - padR;
  const H = height - padT - padB;
  const scores = data.map(d => d.quality_score);
  const minS = Math.max(0, Math.min(...scores) - 10);
  const maxS = Math.min(100, Math.max(...scores) + 10);

  const toX = (i: number) => padL + (i / Math.max(data.length - 1, 1)) * W;
  const toY = (s: number) => padT + H - ((s - minS) / (maxS - minS)) * H;

  const points = data.map((d, i) => `${toX(i)},${toY(d.quality_score)}`).join(' ');

  return (
    <Svg width={width} height={height}>
      {[0, 25, 50, 75, 100].map(v => (
        v >= minS && v <= maxS && (
          <Line key={v} x1={padL} y1={toY(v)} x2={padL + W} y2={toY(v)} stroke={Colors.border} strokeWidth={0.5} />
        )
      ))}
      <Polyline points={points} fill="none" stroke={Colors.primary} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
      {data.map((d, i) => (
        <Circle key={i} cx={toX(i)} cy={toY(d.quality_score)} r={3} fill={scoreColor(d.quality_score)} />
      ))}
      <SvgText x={padL - 2} y={toY(maxS) + 4} fontSize={8} fill={Colors.textMuted} textAnchor="end">{Math.round(maxS)}</SvgText>
      <SvgText x={padL - 2} y={toY(minS) + 4} fontSize={8} fill={Colors.textMuted} textAnchor="end">{Math.round(minS)}</SvgText>
      <SvgText x={padL} y={height - 4} fontSize={8} fill={Colors.textMuted}>{data[0]?.date?.slice(5)}</SvgText>
      <SvgText x={padL + W} y={height - 4} fontSize={8} fill={Colors.textMuted} textAnchor="end">{data[data.length - 1]?.date?.slice(5)}</SvgText>
    </Svg>
  );
}
