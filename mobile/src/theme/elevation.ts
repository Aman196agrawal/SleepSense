import { Platform, ViewStyle } from 'react-native';

// Soft glow shadows tinted with the brand for a "lit" look.
export const Elevation = {
  e1: Platform.select<ViewStyle>({
    ios:     { shadowColor: '#000', shadowOpacity: 0.25, shadowRadius: 8,  shadowOffset: { width: 0, height: 4 } },
    android: { elevation: 2 },
    default: {},
  })!,
  e2: Platform.select<ViewStyle>({
    ios:     { shadowColor: '#000', shadowOpacity: 0.35, shadowRadius: 14, shadowOffset: { width: 0, height: 8 } },
    android: { elevation: 6 },
    default: {},
  })!,
  e3: Platform.select<ViewStyle>({
    ios:     { shadowColor: '#000', shadowOpacity: 0.45, shadowRadius: 24, shadowOffset: { width: 0, height: 12 } },
    android: { elevation: 12 },
    default: {},
  })!,
  glowViolet: Platform.select<ViewStyle>({
    ios:     { shadowColor: '#A78BFA', shadowOpacity: 0.55, shadowRadius: 22, shadowOffset: { width: 0, height: 0 } },
    android: { elevation: 10 },
    default: {},
  })!,
  glowPink: Platform.select<ViewStyle>({
    ios:     { shadowColor: '#F0ABFC', shadowOpacity: 0.45, shadowRadius: 18, shadowOffset: { width: 0, height: 0 } },
    android: { elevation: 8 },
    default: {},
  })!,
};
