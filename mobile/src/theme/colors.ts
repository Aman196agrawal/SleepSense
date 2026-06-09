// Midnight Aurora palette — deep indigo base, violet→pink aurora signature.
// Token names are preserved so every screen reskins automatically.
export const Colors = {
  // Surfaces
  bg:            '#0B0B1F',  // near-black indigo
  surface:       '#15152E',
  surfaceHigh:   '#1F1F3D',
  surfaceGlass:  'rgba(31,31,61,0.55)',
  border:        '#2A2A4A',
  borderSoft:    'rgba(167,139,250,0.12)',

  // Brand
  primary:       '#A78BFA',  // soft violet
  primaryDark:   '#7C3AED',  // deeper violet for gradient end
  primaryDim:    'rgba(167,139,250,0.16)',
  accent:        '#F0ABFC',  // aurora pink
  accentDim:     'rgba(240,171,252,0.16)',
  indigo:        '#6366F1',  // gradient start
  secondary:     '#60A5FA',  // sky-blue informational accent
  amber:         '#FBBF24',
  danger:        '#F87171',

  // Text
  text:          '#F8FAFC',
  textSub:       '#CBD5E1',
  textMuted:     '#7A7A9A',

  // Score grades (semantic)
  excellent:     '#34D399',  // mint
  good:          '#A78BFA',  // violet (brand)
  fair:          '#FBBF24',  // amber
  poor:          '#FB923C',  // orange
  critical:      '#F87171',  // coral
};

// Reusable gradient stops
export const Gradients = {
  aurora:    ['#6366F1', '#A78BFA', '#F0ABFC'] as const,
  auroraSoft:['#1B1B3D', '#251B40', '#2F1B3D'] as const,
  hero:      ['#15152E', '#1F1B3D', '#2A1F4D'] as const,
  card:      ['#1A1A36', '#15152E'] as const,
  glass:     ['rgba(167,139,250,0.10)', 'rgba(240,171,252,0.04)'] as const,
  cta:       ['#7C3AED', '#A78BFA', '#F0ABFC'] as const,
  danger:    ['#F87171', '#EF4444'] as const,
};

export const gradeColor = (grade?: string | null) => {
  switch (grade) {
    case 'Excellent': return Colors.excellent;
    case 'Good':      return Colors.good;
    case 'Fair':      return Colors.fair;
    case 'Poor':      return Colors.poor;
    case 'Critical':  return Colors.critical;
    default:          return Colors.textMuted;
  }
};

export const scoreColor = (score?: number | null) => {
  if (score == null) return Colors.textMuted;
  if (score >= 90) return Colors.excellent;
  if (score >= 75) return Colors.good;
  if (score >= 60) return Colors.fair;
  if (score >= 40) return Colors.poor;
  return Colors.critical;
};

export const scoreGradient = (score?: number | null): readonly [string, string] => {
  if (score == null) return [Colors.textMuted, Colors.textMuted];
  if (score >= 90) return ['#10B981', '#34D399'];
  if (score >= 75) return ['#7C3AED', '#A78BFA'];
  if (score >= 60) return ['#F59E0B', '#FBBF24'];
  if (score >= 40) return ['#EA580C', '#FB923C'];
  return ['#DC2626', '#F87171'];
};
