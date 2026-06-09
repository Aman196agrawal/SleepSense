import React from 'react';
import { View, ViewStyle, StyleProp, StyleSheet } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Colors, Radii, Elevation } from '../theme';

type Variant = 'glass' | 'hero' | 'plain';

interface Props {
  children: React.ReactNode;
  style?: StyleProp<ViewStyle>;
  variant?: Variant;
  glow?: 'violet' | 'pink' | 'none';
  radius?: number;
  padding?: number;
}

export default function GlassCard({
  children, style, variant = 'glass', glow = 'none', radius = Radii.xl, padding = 20,
}: Props) {
  const glowStyle = glow === 'violet' ? Elevation.glowViolet
                  : glow === 'pink'   ? Elevation.glowPink
                  : Elevation.e2;

  if (variant === 'plain') {
    return (
      <View style={[styles.base, { borderRadius: radius, padding, backgroundColor: Colors.surface }, glowStyle, style]}>
        {children}
      </View>
    );
  }

  const colors = variant === 'hero'
    ? (['#1F1B40', '#2A1F4D', '#1F1B40'] as const)
    : (['rgba(167,139,250,0.08)', 'rgba(31,31,61,0.85)'] as const);

  return (
    <View style={[styles.outer, { borderRadius: radius }, glowStyle, style]}>
      <LinearGradient
        colors={colors}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={[styles.base, { borderRadius: radius, padding }]}
      >
        {/* subtle inner highlight */}
        <View pointerEvents="none" style={[styles.highlight, { borderRadius: radius }]} />
        {children}
      </LinearGradient>
    </View>
  );
}

const styles = StyleSheet.create({
  outer: {
    overflow: 'visible',
  },
  base: {
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: Colors.borderSoft,
  },
  highlight: {
    position: 'absolute',
    top: 0, left: 0, right: 0, height: 1,
    backgroundColor: 'rgba(255,255,255,0.06)',
  },
});
