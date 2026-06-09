import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet, Platform } from 'react-native';
import { BottomTabBarProps } from '@react-navigation/bottom-tabs';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Colors, Radii, Gradients, Elevation } from '../theme';

const ICONS: Record<string, { d: keyof typeof Ionicons.glyphMap; f: keyof typeof Ionicons.glyphMap }> = {
  Home:    { d: 'home-outline',     f: 'home' },
  Log:     { d: 'leaf-outline',     f: 'leaf' },
  Record:  { d: 'mic-outline',      f: 'mic' },
  History: { d: 'bar-chart-outline',f: 'bar-chart' },
  Profile: { d: 'person-outline',   f: 'person' },
};

export default function FloatingTabBar({ state, descriptors, navigation }: BottomTabBarProps) {
  const insets = useSafeAreaInsets();

  return (
    <View pointerEvents="box-none" style={[styles.wrap, { paddingBottom: Math.max(insets.bottom, 12) }]}>
      <View style={[styles.barOuter, Elevation.e3]}>
        <LinearGradient
          colors={['rgba(31,31,61,0.92)', 'rgba(21,21,46,0.94)']}
          start={{ x: 0, y: 0 }} end={{ x: 0, y: 1 }}
          style={styles.bar}
        >
          {state.routes.map((route, i) => {
            const focused = state.index === i;
            const isFab = route.name === 'Record';
            const { options } = descriptors[route.key];
            const label = options.tabBarLabel ?? options.title ?? route.name;
            const icons = ICONS[route.name] ?? { d: 'ellipse-outline', f: 'ellipse' };

            const onPress = () => {
              const event = navigation.emit({ type: 'tabPress', target: route.key, canPreventDefault: true });
              if (!focused && !event.defaultPrevented) navigation.navigate(route.name as never);
            };

            if (isFab) {
              return (
                <TouchableOpacity
                  key={route.key}
                  onPress={onPress}
                  activeOpacity={0.85}
                  style={styles.fabSlot}
                >
                  <View style={[styles.fab, Elevation.glowViolet]}>
                    <LinearGradient
                      colors={Gradients.cta as any}
                      start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
                      style={styles.fabInner}
                    >
                      <Ionicons name="mic" size={26} color="#fff" />
                    </LinearGradient>
                  </View>
                </TouchableOpacity>
              );
            }

            return (
              <TouchableOpacity
                key={route.key}
                onPress={onPress}
                activeOpacity={0.7}
                style={styles.tab}
              >
                <Ionicons
                  name={focused ? icons.f : icons.d}
                  size={22}
                  color={focused ? Colors.primary : Colors.textMuted}
                />
                <Text style={[styles.label, focused && styles.labelActive]}>
                  {String(label)}
                </Text>
                {focused && <View style={styles.activeDot} />}
              </TouchableOpacity>
            );
          })}
        </LinearGradient>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    position: 'absolute',
    left: 0, right: 0, bottom: 0,
    paddingHorizontal: 16,
    alignItems: 'center',
  },
  barOuter: {
    width: '100%',
    borderRadius: Radii.xxl,
    overflow: 'visible',
  },
  bar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-around',
    height: 68,
    borderRadius: Radii.xxl,
    borderWidth: 1,
    borderColor: Colors.borderSoft,
    paddingHorizontal: 8,
    overflow: 'hidden',
  },
  tab: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 3,
  },
  label: {
    color: Colors.textMuted,
    fontSize: 10,
    fontWeight: '600',
    letterSpacing: 0.2,
  },
  labelActive: {
    color: Colors.primary,
  },
  activeDot: {
    position: 'absolute',
    top: 6,
    width: 4, height: 4, borderRadius: 2,
    backgroundColor: Colors.primary,
  },
  fabSlot: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  fab: {
    width: 60, height: 60, borderRadius: 30,
    marginTop: -34,
    padding: 3,
    backgroundColor: Colors.bg,
    overflow: 'visible',
    ...Platform.select({
      ios: { shadowColor: '#A78BFA', shadowOpacity: 0.6, shadowRadius: 18, shadowOffset: { width: 0, height: 0 } },
      android: { elevation: 12 },
    }),
  },
  fabInner: {
    flex: 1,
    borderRadius: 30,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
