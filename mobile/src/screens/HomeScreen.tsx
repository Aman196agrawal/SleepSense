import React, { useEffect, useState, useCallback } from 'react';
import { View, Text, ScrollView, StyleSheet, TouchableOpacity, RefreshControl } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Gradients, Radii, Spacing, Elevation } from '../theme';
import { useAuthStore } from '../store/authStore';
import * as AnalyticsAPI from '../api/analytics.api';
import ScoreRing      from '../components/ScoreRing';
import StatCard       from '../components/StatCard';
import InsightCard    from '../components/InsightCard';
import GlassCard      from '../components/GlassCard';
import IconBadge      from '../components/IconBadge';
import GradientButton from '../components/GradientButton';
import AuroraBackground from '../components/AuroraBackground';
import Skeleton       from '../components/Skeleton';

export default function HomeScreen({ navigation }: any) {
  const { user }       = useAuthStore();
  const [session, setSession]     = useState<any>(null);
  const [insights, setInsights]   = useState<any[]>([]);
  const [weekly, setWeekly]       = useState<any>(null);
  const [streak, setStreak]       = useState<any>(null);
  const [correlations, setCorrelations] = useState<any[]>([]);
  const [loading, setLoading]     = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const [loadError, setLoadError] = useState(false);

  const load = useCallback(async () => {
    setLoadError(false);
    try {
      const [sessRes, insRes, wkRes, streakRes, corrRes] = await Promise.all([
        AnalyticsAPI.getSessions(1),
        AnalyticsAPI.getInsights(),
        AnalyticsAPI.getWeeklySummary(),
        AnalyticsAPI.getStreak(),
        AnalyticsAPI.getLifestyleCorrelations(),
      ]);
      setSession(sessRes.data.sessions?.[0] ?? null);
      setInsights(insRes.data.slice(0, 3));
      setWeekly(wkRes.data);
      setStreak(streakRes.data);
      setCorrelations(corrRes.data?.correlations?.slice(0, 2) ?? []);
    } catch { setLoadError(true); }
    finally { setLoading(false); setRefreshing(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const onRefresh = () => { setRefreshing(true); load(); };

  const hour = new Date().getHours();
  const greeting = hour < 5 ? 'Sweet dreams' : hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
  const firstName = (user?.display_name ?? 'Sleeper').split(' ')[0];

  return (
    <AuroraBackground style={{ flex: 1 }}>
      <SafeAreaView style={{ flex: 1 }} edges={['top']}>
        <ScrollView
          contentContainerStyle={styles.container}
          showsVerticalScrollIndicator={false}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.primary} />
          }
        >
          {/* Header */}
          <View style={styles.header}>
            <View style={{ flex: 1 }}>
              <Text style={styles.greeting}>{greeting},</Text>
              <Text style={styles.name}>{firstName}</Text>
            </View>
            <TouchableOpacity style={styles.bell} accessibilityLabel="Notifications" accessible>
              <Ionicons name="notifications-outline" size={20} color={Colors.text} />
            </TouchableOpacity>
          </View>

          {loadError && (
            <View style={styles.errorBanner}>
              <Ionicons name="cloud-offline-outline" size={16} color={Colors.danger} />
              <Text style={styles.errorBannerText}>Couldn't load your data. Pull down to retry.</Text>
            </View>
          )}

          {/* Hero card */}
          {loading ? (
            <HeroSkeleton />
          ) : session ? (
            <GlassCard variant="hero" glow="violet" radius={Radii.xxl} padding={Spacing.x6} style={{ marginBottom: Spacing.x4 }}>
              <View style={styles.heroLabelRow}>
                <Text style={styles.overline}>Last Night</Text>
                <Text style={styles.heroDate}>
                  {new Date(session.started_at).toLocaleDateString('en-IN', { weekday: 'long', month: 'short', day: 'numeric' })}
                </Text>
              </View>
              <View style={{ alignItems: 'center', paddingVertical: 8, marginBottom: 8 }}>
                <ScoreRing
                  score={session.sleep_quality_score ?? 0}
                  grade={session.sleep_quality_grade}
                  size={200}
                />
              </View>
              <View style={styles.statsRow}>
                <StatCard icon="time-outline"        label="Duration"  value={`${Math.floor((session.duration_minutes ?? 0) / 60)}h ${(session.duration_minutes ?? 0) % 60}m`} color={Colors.secondary} />
                <StatCard icon="pulse-outline"       label="Snoring"   value={`${session.snoring_percentage ?? 0}%`}    color={Colors.accent} />
                <StatCard icon="flash-outline"       label="Intensity" value={`${Math.round(session.avg_snore_intensity ?? 0)}`}  color={Colors.amber} />
              </View>
              <TouchableOpacity
                style={styles.detailBtn}
                onPress={() => navigation.navigate('SessionDetail', { sessionId: session.id })}
              >
                <Text style={styles.detailBtnText}>View Full Report</Text>
                <Ionicons name="arrow-forward" size={14} color={Colors.primary} />
              </TouchableOpacity>
            </GlassCard>
          ) : (
            <GlassCard variant="hero" glow="pink" radius={Radii.xxl} padding={Spacing.x8} style={{ marginBottom: Spacing.x4, alignItems: 'center' }}>
              <View style={styles.emptyMoon}>
                <Ionicons name="moon" size={36} color={Colors.primary} />
              </View>
              <Text style={styles.emptyTitle}>Your first night awaits</Text>
              <Text style={styles.emptySub}>
                Tap record to start tracking. We'll surface your Sleep Quality Score and personalised insights by morning.
              </Text>
              <GradientButton
                title="Start Recording"
                icon="mic"
                onPress={() => navigation.navigate('Record')}
                style={{ marginTop: Spacing.x4, minWidth: 200 }}
                size="lg"
              />
            </GlassCard>
          )}

          {/* Weekly snapshot */}
          {loading ? (
            <Skeleton height={96} radius={Radii.xl} style={{ marginBottom: Spacing.x4 }} />
          ) : weekly && (
            <GlassCard variant="glass" radius={Radii.xl} padding={Spacing.x5} style={{ marginBottom: Spacing.x4 }}>
              <Text style={styles.cardHeader}>This Week</Text>
              <View style={styles.weekRow}>
                <WeekStat value={String(weekly.nights_recorded)} label="nights" />
                <Divider />
                <WeekStat value={String(weekly.avg_quality_score)} label="avg score" tint={Colors.primary} />
                <Divider />
                <WeekStat
                  value={`${weekly.vs_previous_week?.quality_change >= 0 ? '+' : ''}${weekly.vs_previous_week?.quality_change ?? 0}`}
                  label="vs last week"
                  tint={weekly.vs_previous_week?.quality_change >= 0 ? Colors.excellent : Colors.danger}
                />
              </View>
            </GlassCard>
          )}

          {/* Streak banner */}
          {!loading && streak && streak.current_streak > 0 && (
            <View style={[styles.streakBanner, Elevation.glowPink]}>
              <LinearGradient
                colors={['rgba(251,191,36,0.18)', 'rgba(240,171,252,0.10)']}
                style={styles.streakInner}
              >
                <Text style={styles.streakEmoji}>🔥</Text>
                <View style={{ flex: 1 }}>
                  <Text style={styles.streakTitle}>{streak.current_streak}-night streak</Text>
                  <Text style={styles.streakSub}>Longest: {streak.longest_streak} · Total: {streak.total_nights_recorded}</Text>
                </View>
              </LinearGradient>
            </View>
          )}

          {/* Log Today */}
          {!loading && (
            <TouchableOpacity
              activeOpacity={0.85}
              style={styles.logBanner}
              onPress={() => navigation.navigate('Log')}
            >
              <IconBadge icon="leaf-outline" color={Colors.excellent} size={40} />
              <View style={{ flex: 1 }}>
                <Text style={styles.logBannerTitle}>Log today's lifestyle</Text>
                <Text style={styles.logBannerSub}>caffeine · alcohol · exercise · stress</Text>
              </View>
              <Ionicons name="chevron-forward" size={18} color={Colors.textMuted} />
            </TouchableOpacity>
          )}

          {/* Insights */}
          {!loading && insights.length > 0 && (
            <View style={{ marginTop: Spacing.x2 }}>
              <SectionHeader title="Insights" icon="sparkles" />
              {insights.map(ins => (
                <InsightCard key={ins.id} title={ins.title} body={ins.body} type={ins.insight_type} />
              ))}
            </View>
          )}

          {!loading && correlations.length > 0 && (
            <View style={{ marginTop: Spacing.x2 }}>
              <SectionHeader title="Lifestyle Impact" icon="analytics" />
              {correlations.map((c: any, i: number) => (
                <View key={i} style={styles.corrCard}>
                  <IconBadge icon="trending-up-outline" color={Colors.secondary} size={36} />
                  <View style={{ flex: 1 }}>
                    <Text style={styles.corrTitle}>{c.title}</Text>
                    <Text style={styles.corrBody}>{c.body}</Text>
                  </View>
                </View>
              ))}
            </View>
          )}
        </ScrollView>
      </SafeAreaView>
    </AuroraBackground>
  );
}

// ── helpers ────────────────────────────────────────────────────────────────

const WeekStat = ({ value, label, tint }: { value: string; label: string; tint?: string }) => (
  <View style={styles.weekStat}>
    <Text style={[styles.weekVal, tint && { color: tint }]}>{value}</Text>
    <Text style={styles.weekLbl}>{label}</Text>
  </View>
);

const Divider = () => <View style={styles.divider} />;

const SectionHeader = ({ title, icon }: { title: string; icon: keyof typeof Ionicons.glyphMap }) => (
  <View style={styles.sectionRow}>
    <Ionicons name={icon} size={14} color={Colors.primary} />
    <Text style={styles.sectionTitle}>{title}</Text>
  </View>
);

const HeroSkeleton = () => (
  <View style={{ marginBottom: 16 }}>
    <Skeleton height={320} radius={Radii.xxl} />
  </View>
);

// ── styles ─────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  container:    { padding: Spacing.x5, paddingBottom: 120 },
  header:       { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: Spacing.x6 },
  greeting:     { color: Colors.textSub, fontSize: 13, fontWeight: '500' },
  name:         { color: Colors.text, fontSize: 28, fontWeight: '800', marginTop: 2, letterSpacing: -0.8 },
  bell:         {
    width: 44, height: 44, borderRadius: 22,
    backgroundColor: 'rgba(167,139,250,0.10)',
    borderWidth: 1, borderColor: Colors.borderSoft,
    alignItems: 'center', justifyContent: 'center',
  },

  heroLabelRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 },
  overline:     { color: Colors.primary, fontSize: 11, fontWeight: '700', letterSpacing: 2, textTransform: 'uppercase' },
  heroDate:     { color: Colors.textSub, fontSize: 13, fontWeight: '600' },

  statsRow:     { flexDirection: 'row', gap: 10, marginTop: 4 },
  detailBtn:    {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6,
    marginTop: Spacing.x5,
    paddingVertical: 12,
    borderRadius: Radii.md,
    backgroundColor: 'rgba(167,139,250,0.12)',
    borderWidth: 1, borderColor: Colors.primary + '55',
  },
  detailBtnText:{ color: Colors.primary, fontWeight: '700', fontSize: 14, letterSpacing: 0.2 },

  emptyMoon:    {
    width: 76, height: 76, borderRadius: 38,
    backgroundColor: Colors.primary + '22',
    alignItems: 'center', justifyContent: 'center', marginBottom: 16,
  },
  emptyTitle:   { color: Colors.text, fontSize: 20, fontWeight: '800', letterSpacing: -0.4 },
  emptySub:     { color: Colors.textSub, textAlign: 'center', lineHeight: 22, fontSize: 14, maxWidth: 280, marginTop: 8 },

  cardHeader:   { color: Colors.text, fontWeight: '700', fontSize: 15, marginBottom: 14, letterSpacing: -0.2 },
  weekRow:      { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-around' },
  weekStat:     { alignItems: 'center', flex: 1 },
  weekVal:      { color: Colors.text, fontWeight: '800', fontSize: 24, letterSpacing: -0.8 },
  weekLbl:      { color: Colors.textMuted, fontSize: 11, marginTop: 4, fontWeight: '600', letterSpacing: 0.4 },
  divider:      { width: 1, height: 36, backgroundColor: Colors.borderSoft },

  streakBanner: { borderRadius: Radii.lg, overflow: 'hidden', marginBottom: Spacing.x4 },
  streakInner:  { flexDirection: 'row', alignItems: 'center', gap: 14, padding: 14, borderWidth: 1, borderColor: Colors.amber + '44', borderRadius: Radii.lg },
  streakEmoji:  { fontSize: 26 },
  streakTitle:  { color: Colors.text, fontWeight: '800', fontSize: 14, letterSpacing: -0.2 },
  streakSub:    { color: Colors.textSub, fontSize: 12, marginTop: 2 },

  logBanner:    {
    flexDirection: 'row', alignItems: 'center', gap: 12,
    backgroundColor: 'rgba(167,139,250,0.06)',
    borderRadius: Radii.lg,
    padding: 14,
    marginBottom: Spacing.x5,
    borderWidth: 1, borderColor: Colors.borderSoft,
  },
  logBannerTitle:{ color: Colors.text, fontWeight: '700', fontSize: 14 },
  logBannerSub:  { color: Colors.textMuted, fontSize: 11, marginTop: 2, fontWeight: '500' },

  sectionRow:   { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 12, marginTop: 6 },
  sectionTitle: { color: Colors.text, fontWeight: '700', fontSize: 15, letterSpacing: -0.2 },

  corrCard:     {
    flexDirection: 'row', alignItems: 'flex-start', gap: 12,
    backgroundColor: 'rgba(96,165,250,0.06)',
    borderRadius: Radii.lg, padding: 14, marginBottom: 10,
    borderWidth: 1, borderColor: Colors.secondary + '33',
  },
  corrTitle:    { color: Colors.text, fontWeight: '700', fontSize: 13, marginBottom: 4 },
  corrBody:     { color: Colors.textSub, fontSize: 12, lineHeight: 18 },
  errorBanner:  { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: Colors.danger + '18', borderRadius: Radii.lg, padding: 12, marginBottom: Spacing.x4, borderWidth: 1, borderColor: Colors.danger + '33' },
  errorBannerText: { color: Colors.danger, fontSize: 13, flex: 1 },
});
