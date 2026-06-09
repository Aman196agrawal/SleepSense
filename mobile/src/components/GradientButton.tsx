import React from 'react';
import { TouchableOpacity, Text, StyleSheet, View, ActivityIndicator, ViewStyle, StyleProp } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Gradients, Radii, Elevation } from '../theme';

interface Props {
  title: string;
  onPress: () => void;
  icon?: keyof typeof Ionicons.glyphMap;
  loading?: boolean;
  disabled?: boolean;
  variant?: 'primary' | 'ghost';
  size?: 'md' | 'lg';
  style?: StyleProp<ViewStyle>;
  glow?: boolean;
}

export default function GradientButton({
  title, onPress, icon, loading, disabled, variant = 'primary', size = 'md', style, glow = true,
}: Props) {
  const isPrimary = variant === 'primary';
  const padV = size === 'lg' ? 16 : 13;
  const fontSize = size === 'lg' ? 16 : 15;

  if (!isPrimary) {
    return (
      <TouchableOpacity
        activeOpacity={0.8}
        disabled={disabled || loading}
        onPress={onPress}
        style={[
          styles.ghost,
          { paddingVertical: padV, opacity: disabled ? 0.5 : 1 },
          style,
        ]}
      >
        {loading ? <ActivityIndicator size="small" color={Colors.primary} /> : (
          <View style={styles.inner}>
            {icon && <Ionicons name={icon} size={16} color={Colors.primary} />}
            <Text style={[styles.ghostText, { fontSize }]}>{title}</Text>
          </View>
        )}
      </TouchableOpacity>
    );
  }

  return (
    <TouchableOpacity
      activeOpacity={0.85}
      disabled={disabled || loading}
      onPress={onPress}
      style={[
        { borderRadius: Radii.lg, overflow: 'visible', opacity: disabled ? 0.5 : 1 },
        glow ? Elevation.glowViolet : null,
        style,
      ]}
    >
      <LinearGradient
        colors={Gradients.cta as any}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 0 }}
        style={[styles.primary, { paddingVertical: padV, borderRadius: Radii.lg }]}
      >
        {loading ? (
          <ActivityIndicator size="small" color="#fff" />
        ) : (
          <View style={styles.inner}>
            {icon && <Ionicons name={icon} size={18} color="#fff" />}
            <Text style={[styles.primaryText, { fontSize }]}>{title}</Text>
          </View>
        )}
      </LinearGradient>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  primary:     { alignItems: 'center', justifyContent: 'center' },
  primaryText: { color: '#fff', fontWeight: '700', letterSpacing: 0.2 },
  ghost:       { alignItems: 'center', justifyContent: 'center', borderRadius: Radii.lg, borderWidth: 1, borderColor: Colors.primary + '88' },
  ghostText:   { color: Colors.primary, fontWeight: '700' },
  inner:       { flexDirection: 'row', alignItems: 'center', gap: 8 },
});
