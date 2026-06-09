import React from 'react';
import { View, StyleSheet, ViewStyle, StyleProp } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import Svg, { Defs, RadialGradient, Stop, Rect } from 'react-native-svg';
import { Colors } from '../theme';

interface Props {
  children?: React.ReactNode;
  style?: StyleProp<ViewStyle>;
  intensity?: 'soft' | 'bold';
}

// Layered background: dark indigo base + two radial aurora blobs (violet top-left, pink bottom-right).
export default function AuroraBackground({ children, style, intensity = 'soft' }: Props) {
  const opacityViolet = intensity === 'bold' ? 0.55 : 0.35;
  const opacityPink   = intensity === 'bold' ? 0.45 : 0.25;

  return (
    <View style={[styles.wrap, style]}>
      <LinearGradient
        colors={[Colors.bg, '#0F0E26', Colors.bg]}
        style={StyleSheet.absoluteFill}
        start={{ x: 0, y: 0 }}
        end={{ x: 0, y: 1 }}
      />
      <Svg style={StyleSheet.absoluteFill}>
        <Defs>
          <RadialGradient id="violetBlob" cx="20%" cy="10%" rx="65%" ry="55%">
            <Stop offset="0%" stopColor="#7C3AED" stopOpacity={opacityViolet} />
            <Stop offset="60%" stopColor="#7C3AED" stopOpacity="0" />
          </RadialGradient>
          <RadialGradient id="pinkBlob" cx="100%" cy="90%" rx="70%" ry="60%">
            <Stop offset="0%" stopColor="#F0ABFC" stopOpacity={opacityPink} />
            <Stop offset="65%" stopColor="#F0ABFC" stopOpacity="0" />
          </RadialGradient>
          <RadialGradient id="indigoBlob" cx="80%" cy="20%" rx="45%" ry="35%">
            <Stop offset="0%" stopColor="#6366F1" stopOpacity={opacityViolet * 0.8} />
            <Stop offset="70%" stopColor="#6366F1" stopOpacity="0" />
          </RadialGradient>
        </Defs>
        <Rect x="0" y="0" width="100%" height="100%" fill="url(#violetBlob)" />
        <Rect x="0" y="0" width="100%" height="100%" fill="url(#pinkBlob)" />
        <Rect x="0" y="0" width="100%" height="100%" fill="url(#indigoBlob)" />
      </Svg>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: Colors.bg },
});
