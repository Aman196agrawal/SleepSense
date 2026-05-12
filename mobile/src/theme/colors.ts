export const Colors = {
  bg:            '#0A1628',
  surface:       '#112240',
  surfaceHigh:   '#1A3660',
  border:        '#1E3A5F',
  primary:       '#00BFA5',
  primaryDark:   '#00897B',
  secondary:     '#3D8EF0',
  amber:         '#F59E0B',
  danger:        '#F43F5E',
  text:          '#FFFFFF',
  textSub:       '#94A3B8',
  textMuted:     '#64748B',
  excellent:     '#22C55E',
  good:          '#3D8EF0',
  fair:          '#F59E0B',
  poor:          '#F97316',
  critical:      '#F43F5E',
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
  if (!score) return Colors.textMuted;
  if (score >= 90) return Colors.excellent;
  if (score >= 75) return Colors.good;
  if (score >= 60) return Colors.fair;
  if (score >= 40) return Colors.poor;
  return Colors.critical;
};
