import { Platform, TextStyle } from 'react-native';
import { Colors } from './colors';

const baseFont = Platform.select({ ios: 'System', android: 'sans-serif' });

export const Type: Record<string, TextStyle> = {
  display:   { fontFamily: baseFont, fontSize: 56, fontWeight: '800', letterSpacing: -1.5, color: Colors.text },
  hero:      { fontFamily: baseFont, fontSize: 40, fontWeight: '800', letterSpacing: -1,   color: Colors.text },
  h1:        { fontFamily: baseFont, fontSize: 28, fontWeight: '800', letterSpacing: -0.6, color: Colors.text },
  h2:        { fontFamily: baseFont, fontSize: 22, fontWeight: '700', letterSpacing: -0.4, color: Colors.text },
  h3:        { fontFamily: baseFont, fontSize: 18, fontWeight: '700', letterSpacing: -0.2, color: Colors.text },
  title:     { fontFamily: baseFont, fontSize: 16, fontWeight: '700', color: Colors.text },
  body:      { fontFamily: baseFont, fontSize: 15, fontWeight: '500', color: Colors.text },
  bodySub:   { fontFamily: baseFont, fontSize: 14, fontWeight: '500', color: Colors.textSub },
  caption:   { fontFamily: baseFont, fontSize: 12, fontWeight: '500', color: Colors.textMuted, letterSpacing: 0.1 },
  overline:  { fontFamily: baseFont, fontSize: 11, fontWeight: '700', color: Colors.textMuted, letterSpacing: 1.4, textTransform: 'uppercase' },
  numericLg: { fontFamily: baseFont, fontSize: 48, fontWeight: '800', letterSpacing: -1.5, color: Colors.text },
  numericMd: { fontFamily: baseFont, fontSize: 24, fontWeight: '800', letterSpacing: -0.4, color: Colors.text },
};
