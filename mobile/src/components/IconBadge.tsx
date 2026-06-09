import React from 'react';
import { View, StyleSheet, ViewStyle, StyleProp } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Radii } from '../theme';

interface Props {
  icon: keyof typeof Ionicons.glyphMap;
  color?: string;
  size?: number;
  style?: StyleProp<ViewStyle>;
}

// Pill-shaped icon with brand-tinted background.
export default function IconBadge({ icon, color = Colors.primary, size = 36, style }: Props) {
  const inner = Math.round(size * 0.55);
  return (
    <View
      style={[
        styles.wrap,
        { width: size, height: size, borderRadius: Radii.md, backgroundColor: color + '22' },
        style,
      ]}
    >
      <Ionicons name={icon} size={inner} color={color} />
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { alignItems: 'center', justifyContent: 'center' },
});
