import React, { useRef, useState } from 'react';
import { View, Text, StyleSheet, FlatList, Dimensions, TouchableOpacity, NativeScrollEvent, NativeSyntheticEvent } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { Colors } from '../theme/colors';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { AuthStackParams } from '../navigation/AuthNavigator';

const { width } = Dimensions.get('window');

const slides = [
  {
    icon: 'moon',
    title: 'Track Your Sleep',
    body: 'Simply place your phone nearby. SleepSense records and analyses your sleep all night — no extra hardware needed.',
  },
  {
    icon: 'analytics',
    title: 'AI-Powered Insights',
    body: 'Our CNN model classifies every sound — snoring, breathing, silence — and gives you a real Sleep Quality Score each morning.',
  },
  {
    icon: 'sunny',
    title: 'Wake Up Better',
    body: 'Get personalised tips based on your patterns. See trends, set goals, and sleep your way to a healthier life.',
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
    <LinearGradient colors={['#0A1628', '#112240']} style={styles.container}>
      <TouchableOpacity style={styles.skipTop} onPress={() => navigation.replace('Login')}>
        <Text style={styles.skipText}>Skip</Text>
      </TouchableOpacity>

      <FlatList
        ref={ref}
        data={slides}
        horizontal
        pagingEnabled
        scrollEnabled
        showsHorizontalScrollIndicator={false}
        keyExtractor={(_, i) => String(i)}
        onMomentumScrollEnd={onMomentumScrollEnd}
        renderItem={({ item }) => (
          <View style={styles.slide}>
            <View style={styles.iconWrap}>
              <Ionicons name={item.icon as any} size={72} color={Colors.primary} />
            </View>
            <Text style={styles.title}>{item.title}</Text>
            <Text style={styles.body}>{item.body}</Text>
          </View>
        )}
      />

      <View style={styles.dots}>
        {slides.map((_, i) => (
          <TouchableOpacity key={i} onPress={() => goTo(i)}>
            <View style={[styles.dot, i === index && styles.dotActive]} />
          </TouchableOpacity>
        ))}
      </View>

      <TouchableOpacity style={styles.btn} onPress={next}>
        <LinearGradient colors={[Colors.primary, Colors.primaryDark]} style={styles.btnInner}>
          <Text style={styles.btnText}>{index < slides.length - 1 ? 'Next' : 'Get Started'}</Text>
          <Ionicons name="arrow-forward" size={18} color="#fff" />
        </LinearGradient>
      </TouchableOpacity>
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  skipTop:   { position: 'absolute', top: 56, right: 24, zIndex: 10, padding: 8 },
  skipText:  { color: Colors.textMuted, fontSize: 14 },
  slide:     { width, flex: 1, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 40, paddingTop: 80 },
  iconWrap:  { width: 120, height: 120, borderRadius: 60, backgroundColor: Colors.surfaceHigh, alignItems: 'center', justifyContent: 'center', marginBottom: 40 },
  title:     { fontSize: 28, fontWeight: '800', color: Colors.text, textAlign: 'center', marginBottom: 16 },
  body:      { fontSize: 16, color: Colors.textSub, textAlign: 'center', lineHeight: 26 },
  dots:      { flexDirection: 'row', justifyContent: 'center', alignItems: 'center', paddingBottom: 24, gap: 4 },
  dot:       { width: 8, height: 8, borderRadius: 4, backgroundColor: Colors.border },
  dotActive: { backgroundColor: Colors.primary, width: 24 },
  btn:       { marginHorizontal: 32, marginBottom: 20, borderRadius: 14, overflow: 'hidden' },
  btnInner:  { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', paddingVertical: 16, gap: 8 },
  btnText:   { color: '#fff', fontWeight: '700', fontSize: 16 },
});
