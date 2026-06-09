import React, { useRef, useState, useEffect } from 'react';
import { View, Text, StyleSheet, FlatList, Dimensions, TouchableOpacity, NativeScrollEvent, NativeSyntheticEvent, Animated, Easing } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Radii, Spacing } from '../theme';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { AuthStackParams } from '../navigation/AuthNavigator';
import AuroraBackground from '../components/AuroraBackground';
import GradientButton from '../components/GradientButton';

const { width } = Dimensions.get('window');

type Slide = { icon: keyof typeof Ionicons.glyphMap; title: string; body: string; accent: string };

const slides: Slide[] = [
  {
    icon:  'moon',
    title: 'Track Your Sleep',
    body:  'Place your phone nearby. SleepSense quietly records and analyses every night — no extra hardware needed.',
    accent:'#A78BFA',
  },
  {
    icon:  'pulse',
    title: 'Smart Sound Detection',
    body:  'Loudness-based detection tags each segment as snoring, breathing or silence and computes a Sleep Quality Score by morning.',
    accent:'#F0ABFC',
  },
  {
    icon:  'sunny',
    title: 'Wake Up Better',
    body:  'Get personalised tips from your patterns. See trends, set goals, and sleep your way to a healthier life.',
    accent:'#FBBF24',
  },
];

type Props = { navigation: NativeStackNavigationProp<AuthStackParams, 'Onboarding'> };

export default function OnboardingScreen({ navigation }: Props) {
  const ref = useRef<FlatList>(null);
  const [index, setIndex] = useState(0);

  const goTo = (i: number) => {
    ref.current?.scrollToIndex({ index: i, animated: true });
    setIndex(i);
  };

  const next = () => {
    if (index < slides.length - 1) goTo(index + 1);
    else navigation.replace('Login');
  };

  const onMomentumScrollEnd = (e: NativeSyntheticEvent<NativeScrollEvent>) => {
    const i = Math.round(e.nativeEvent.contentOffset.x / width);
    if (i !== index) setIndex(i);
  };

  return (
    <AuroraBackground style={{ flex: 1 }} intensity="bold">
      <SafeAreaView style={{ flex: 1 }}>
        <View style={styles.topRow}>
          <View style={styles.brandRow}>
            <View style={styles.brandMark}><Ionicons name="moon" size={14} color={Colors.primary} /></View>
            <Text style={styles.brandText}>SleepSense</Text>
          </View>
          <TouchableOpacity style={styles.skip} onPress={() => navigation.replace('Login')}>
            <Text style={styles.skipText}>Skip</Text>
          </TouchableOpacity>
        </View>

        <FlatList
          ref={ref}
          data={slides}
          horizontal
          pagingEnabled
          showsHorizontalScrollIndicator={false}
          keyExtractor={(_, i) => String(i)}
          onMomentumScrollEnd={onMomentumScrollEnd}
          renderItem={({ item }) => <Slide slide={item} />}
        />

        <View style={styles.dots}>
          {slides.map((_, i) => (
            <TouchableOpacity key={i} onPress={() => goTo(i)} hitSlop={8}>
              <View style={[styles.dot, i === index && styles.dotActive]} />
            </TouchableOpacity>
          ))}
        </View>

        <View style={styles.btnWrap}>
          <GradientButton
            title={index < slides.length - 1 ? 'Continue' : 'Get Started'}
            icon="arrow-forward"
            onPress={next}
            size="lg"
          />
        </View>
      </SafeAreaView>
    </AuroraBackground>
  );
}

const Slide = ({ slide }: { slide: Slide }) => {
  const float = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    Animated.loop(
      Animated.sequence([
        Animated.timing(float, { toValue: 1, duration: 2400, easing: Easing.inOut(Easing.sin), useNativeDriver: true }),
        Animated.timing(float, { toValue: 0, duration: 2400, easing: Easing.inOut(Easing.sin), useNativeDriver: true }),
      ])
    ).start();
  }, [float]);
  const translateY = float.interpolate({ inputRange: [0, 1], outputRange: [0, -10] });

  return (
    <View style={styles.slide}>
      <Animated.View style={[styles.iconOuter, { transform: [{ translateY }], shadowColor: slide.accent }]}>
        <View style={[styles.iconInner, { backgroundColor: slide.accent + '1A', borderColor: slide.accent + '44' }]}>
          <View style={[styles.iconCore, { backgroundColor: slide.accent + '26' }]}>
            <Ionicons name={slide.icon} size={64} color={slide.accent} />
          </View>
        </View>
      </Animated.View>
      <Text style={styles.title}>{slide.title}</Text>
      <Text style={styles.body}>{slide.body}</Text>
    </View>
  );
};

const styles = StyleSheet.create({
  topRow:     { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: 24, paddingTop: 12 },
  brandRow:   { flexDirection: 'row', alignItems: 'center', gap: 8 },
  brandMark:  { width: 28, height: 28, borderRadius: 14, backgroundColor: Colors.primary + '22', borderWidth: 1, borderColor: Colors.primary + '55', alignItems: 'center', justifyContent: 'center' },
  brandText:  { color: Colors.text, fontSize: 14, fontWeight: '700', letterSpacing: -0.2 },
  skip:       { padding: 8 },
  skipText:   { color: Colors.textSub, fontSize: 14, fontWeight: '600' },

  slide:      { width, flex: 1, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 36 },
  iconOuter:  {
    width: 200, height: 200, borderRadius: 100,
    alignItems: 'center', justifyContent: 'center',
    marginBottom: 48,
    shadowOpacity: 0.4, shadowRadius: 30, shadowOffset: { width: 0, height: 0 },
    elevation: 14,
  },
  iconInner:  { width: 168, height: 168, borderRadius: 84, alignItems: 'center', justifyContent: 'center', borderWidth: 1 },
  iconCore:   { width: 124, height: 124, borderRadius: 62, alignItems: 'center', justifyContent: 'center' },
  title:      { fontSize: 32, fontWeight: '800', color: Colors.text, textAlign: 'center', marginBottom: 16, letterSpacing: -0.8 },
  body:       { fontSize: 15, color: Colors.textSub, textAlign: 'center', lineHeight: 24, maxWidth: 320 },

  dots:       { flexDirection: 'row', justifyContent: 'center', alignItems: 'center', paddingVertical: 20, gap: 6 },
  dot:        { width: 6, height: 6, borderRadius: 3, backgroundColor: Colors.border },
  dotActive:  { backgroundColor: Colors.primary, width: 24, height: 6, borderRadius: 3 },

  btnWrap:    { paddingHorizontal: 32, paddingBottom: Spacing.x6 },
});
