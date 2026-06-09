import React, { useEffect, useRef, useState } from 'react';
import { View, Text, Animated, Easing, StyleSheet } from 'react-native';
import Svg, { Circle, Defs, LinearGradient as SvgLinearGradient, Stop } from 'react-native-svg';
import { Colors, scoreGradient, scoreColor } from '../theme';

const AnimatedCircle = Animated.createAnimatedComponent(Circle);

interface Props {
  score: number;
  size?: number;
  grade?: string;
  /** Outer halo glow tinted by score color. */
  halo?: boolean;
}

export default function ScoreRing({ score, size = 180, grade, halo = true }: Props) {
  const stroke   = Math.max(8, Math.round(size * 0.07));
  const r        = (size - stroke) / 2;
  const cx       = size / 2;
  const circumf  = 2 * Math.PI * r;
  const target   = Math.max(0, Math.min(score / 100, 1));
  const [from, to] = scoreGradient(score);
  const color    = scoreColor(score);

  // Animated stroke fill (spring) + animated count-up
  const progress = useRef(new Animated.Value(0)).current;
  const [display, setDisplay] = useState(0);

  useEffect(() => {
    progress.setValue(0);
    Animated.timing(progress, {
      toValue: target,
      duration: 1100,
      easing: Easing.out(Easing.cubic),
      useNativeDriver: false, // we animate SVG props (strokeDashoffset)
    }).start();

    // Count-up using a separate JS timer (svg text inside <Text> is JS-driven)
    const start = Date.now();
    const fromN = 0;
    const toN   = Math.round(score);
    const dur   = 1100;
    let raf: any;
    const tick = () => {
      const t = Math.min(1, (Date.now() - start) / dur);
      const eased = 1 - Math.pow(1 - t, 3);
      setDisplay(Math.round(fromN + (toN - fromN) * eased));
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    tick();
    return () => { if (raf) cancelAnimationFrame(raf); };
  }, [score]);

  const strokeDashoffset = progress.interpolate({
    inputRange:  [0, 1],
    outputRange: [circumf, circumf * (1 - target) + 0.0001],
  });

  return (
    <View style={[styles.container, { width: size, height: size }]}>
      {halo && (
        <View
          pointerEvents="none"
          style={[
            styles.halo,
            {
              width: size + 56, height: size + 56,
              borderRadius: (size + 56) / 2,
              shadowColor: color,
              shadowOpacity: 0.55,
              shadowRadius: 32,
              shadowOffset: { width: 0, height: 0 },
              elevation: 18,
              backgroundColor: color + '11',
            },
          ]}
        />
      )}
      <Svg width={size} height={size} style={StyleSheet.absoluteFill}>
        <Defs>
          <SvgLinearGradient id="ringGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <Stop offset="0%"   stopColor={from} />
            <Stop offset="100%" stopColor={to} />
          </SvgLinearGradient>
        </Defs>
        {/* Track */}
        <Circle
          cx={cx} cy={cx} r={r}
          stroke={Colors.surfaceHigh}
          strokeWidth={stroke}
          fill="none"
        />
        {/* Progress */}
        <AnimatedCircle
          cx={cx} cy={cx} r={r}
          stroke="url(#ringGrad)"
          strokeWidth={stroke}
          fill="none"
          strokeDasharray={`${circumf} ${circumf}`}
          strokeDashoffset={strokeDashoffset as any}
          strokeLinecap="round"
          rotation="-90"
          origin={`${cx},${cx}`}
        />
      </Svg>
      <View style={styles.label}>
        <Text style={{
          fontSize: size * 0.30,
          fontWeight: '800',
          color: Colors.text,
          letterSpacing: -1.5,
          lineHeight: size * 0.34,
        }}>
          {display}
        </Text>
        <Text style={{
          fontSize: size * 0.075,
          color: Colors.textMuted,
          letterSpacing: 2,
          marginTop: 2,
          fontWeight: '700',
        }}>
          / 100
        </Text>
        {grade && (
          <Text style={{
            fontSize: size * 0.085,
            color,
            fontWeight: '700',
            marginTop: 6,
            letterSpacing: 0.4,
          }}>
            {grade.toUpperCase()}
          </Text>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { alignItems: 'center', justifyContent: 'center' },
  halo:      { position: 'absolute', alignSelf: 'center' },
  label:     { alignItems: 'center', justifyContent: 'center' },
});
