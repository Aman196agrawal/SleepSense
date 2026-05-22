import React, { useEffect, useState, useCallback } from 'react';
import { View, Text, ScrollView, StyleSheet, TouchableOpacity, RefreshControl, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { Colors, gradeColor } from '../theme/colors';
import { useAuthStore } from '../store/authStore';
import * as AnalyticsAPI from '../api/analytics.api';
import ScoreRing from '../components/ScoreRing';
import StatCard  from '../components/StatCard';
import InsightCard from '../components/InsightCard';

export default function HomeScreen({ navigation }: any) {
  const { user }       = useAuthStore();
  const [session, setSession]     = useState<any>(null);
  const [insights, setInsights]   = useState<any[]>([]);
  const [weekly, setWeekly]       = useState<any>(null);
  const [streak, setStreak]       = useState<any>(null);
  const [correlations, setCorrelations] = useState<any[]>([]);
  const [loading, setLoading]     = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
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
    } catch {}
    finally { setLoading(false); setRefreshing(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const onRefresh = () => { setRefreshing(true); load(); };

  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';

  if (loading) return (
    <View style={styles.center}><ActivityIndicator color={Colors.primary} size="large" /></View>
  );

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.bg }}>
      <ScrollView
        contentContainerStyle={styles.container}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.primary} />}
      >
        {/* Header */}
        <View style={styles.header}>
          <View>
            <Text style={styles.greeting}>{greeting},</Text>
            <Text style={styles.name}>{user?.display_name ?? 'Sleeper'} 👋</Text>
          </View>
          <Ionicons name="notifications-outline" size={24} color={Colors.textSub} />
        </View>

        {/* Last night score */}
        {session ? (
          <LinearGradient colors={['#112240', '#1A3660']} style={styles.scoreCard}>
            <Text style={styles.cardLabel}>Last Night</Text>
            <Text style={styles.cardDate}>{new Date(session.started_at).toLocaleDateString('en-IN', { weekday: 'long', month: 'short', day: 'numeric' })}</Text>
            <View style={{ alignItems: 'center', paddingVertical: 16 }}>
              <ScoreRing score={session.sleep_quality_score ?? 0} grade={session.sleep_quality_grade} size={160} />
            </View>
            <View style={styles.statsRow}>
              <StatCard icon="time-outline"          label="Duration"     value={`${Math.floor((session.duration_minutes ?? 0) / 60)}h ${(session.duration_minutes ?? 0) % 60}m`} color={Colors.secondary} />
              <StatCard icon="volume-high-outline"   label="Snoring"      value={`${session.snoring_percentage ?? 0}%`}    color={Colors.danger} />
              <StatCard icon="flash-outline"         label="Intensity"    value={`${Math.round(session.avg_snore_intensity ?? 0)}`}  color={Colors.amber} />
            </View>
            <TouchableOpacity
              style={styles.detailBtn}
              onPress={() => navigation.navigate('SessionDetail', { sessionId: session.id })}
            >
              <Text style={styles.detailBtnText}>View Full Report</Text>
              <Ionicons name="arrow-forward" size={14} color={Colors.primary} />
            </TouchableOpacity>
          </LinearGradient>
        ) : (
          <View style={[styles.scoreCard, styles.emptyCard]}>
            <Ionicons name="moon-outline" size={52} color={Colors.primary} />
            <Text style={styles.emptyTitle}>No sessions yet</Text>
            <Text style={styles.emptySub}>Record your first night to see your Sleep Quality Score and personalised insights.</Text>
            <TouchableOpacity
              style={styles.emptyBtn}
              onPress={() => navigation.navigate('Record')}
            >
              <LinearGradient colors={[Colors.primary, Colors.primaryDark]} style={styles.emptyBtnInner}>
                <Ionicons name="mic" size={16} color="#fff" />
                <Text style={styles.emptyBtnText}>Start Recording</Text>
              </LinearGradient>
            </TouchableOpacity>
          </View>
        )}

        {/* Weekly snapshot */}
        {weekly && (
          <View style={styles.weekCard}>
            <Text style={styles.sectionTitle}>This Week</Text>
            <View style={styles.weekRow}>
              <View style={styles.weekStat}>
                <Text style={styles.weekVal}>{weekly.nights_recorded}</Text>
                <Text style={styles.weekLbl}>nights</Text>
              </View>
              <View style={styles.weekStat}>
                <Text style={[styles.weekVal, { color: Colors.primary }]}>{weekly.avg_quality_score}</Text>
                <Text style={styles.weekLbl}>avg score</Text>
              </View>
              <View style={styles.weekStat}>
                <Text style={[styles.weekVal, { color: weekly.vs_previous_week?.quality_change >= 0 ? Colors.excellent : Colors.danger }]}>
                  {weekly.vs_previous_week?.quality_change >= 0 ? '+' : ''}{weekly.vs_previous_week?.quality_change}
                </Text>
                <Text style={styles.weekLbl}>vs last week</Text>
              </View>
            </View>
          </View>
        )}

        {/* Streak banner */}
        {streak && streak.current_streak > 0 && (
          <View style={styles.streakBanner}>
            <Text style={styles.streakEmoji}>🔥</Text>
            <View>
              <Text style={styles.streakTitle}>{streak.current_streak}-night recording streak</Text>
              <Text style={styles.streakSub}>Longest: {streak.longest_streak} nights · Total: {streak.total_nights_recorded}</Text>
            </View>
          </View>
        )}

        {/* Log Today quick action */}
        <TouchableOpacity
          style={styles.logBanner}
          onPress={() => navigation.navigate('Log')}
        >
          <View style={styles.logBannerLeft}>
            <Ionicons name="leaf-outline" size={20} color={Colors.primary} />
            <View>
              <Text style={styles.logBannerTitle}>Log today's lifestyle</Text>
              <Text style={styles.logBannerSub}>caffeine · alcohol · exercise · stress</Text>
            </View>
          </View>
          <Ionicons name="chevron-forward" size={18} color={Colors.textMuted} />
        </TouchableOpacity>

        {/* Insights */}
        {insights.length > 0 && (
          <View style={{ marginTop: 8 }}>
            <Text style={styles.sectionTitle}>Insights</Text>
            {insights.map(ins => (
              <InsightCard key={ins.id} title={ins.title} body={ins.body} type={ins.insight_type} />
            ))}
          </View>
        )}

        {correlations.length > 0 && (
          <View style={{ marginTop: 8 }}>
            <Text style={styles.sectionTitle}>Lifestyle Impact</Text>
            {correlations.map((c: any, i: number) => (
              <View key={i} style={styles.corrCard}>
                <Ionicons name="analytics-outline" size={18} color={Colors.secondary} style={{ marginTop: 2 }} />
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
  );
}

const styles = StyleSheet.create({
  center:       { flex: 1, backgroundColor: Colors.bg, justifyContent: 'center', alignItems: 'center' },
  container:    { padding: 20, paddingBottom: 40 },
  header:       { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24 },
  greeting:     { color: Colors.textSub, fontSize: 14 },
  name:         { color: Colors.text, fontSize: 22, fontWeight: '700', marginTop: 2 },
  scoreCard:    { borderRadius: 20, padding: 20, marginBottom: 16, borderWidth: 1, borderColor: Colors.border },
  emptyCard:    { backgroundColor: Colors.surface, alignItems: 'center', paddingVertical: 40, gap: 12 },
  emptyTitle:   { color: Colors.text, fontSize: 18, fontWeight: '700', marginTop: 4 },
  emptySub:     { color: Colors.textSub, textAlign: 'center', lineHeight: 22, fontSize: 14, maxWidth: 280 },
  emptyBtn:     { borderRadius: 12, overflow: 'hidden', marginTop: 8 },
  emptyBtnInner:{ flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 24, paddingVertical: 12 },
  emptyBtnText: { color: '#fff', fontWeight: '700', fontSize: 15 },
  logBanner:      { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', backgroundColor: Colors.surface, borderRadius: 14, padding: 14, marginBottom: 20, borderWidth: 1, borderColor: Colors.primary + '44' },
  logBannerLeft:  { flexDirection: 'row', alignItems: 'center', gap: 12 },
  logBannerTitle: { color: Colors.text, fontWeight: '600', fontSize: 14 },
  logBannerSub:   { color: Colors.textMuted, fontSize: 11, marginTop: 2 },
  cardLabel:    { color: Colors.textSub, fontSize: 13, marginBottom: 2 },
  cardDate:     { color: Colors.text, fontWeight: '600', fontSize: 15 },
  statsRow:     { flexDirection: 'row', gap: 8, marginTop: 8 },
  detailBtn:    { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, marginTop: 16, paddingVertical: 10, borderRadius: 10, borderWidth: 1, borderColor: Colors.primary },
  detailBtnText:{ color: Colors.primary, fontWeight: '600', fontSize: 14 },
  weekCard:     { backgroundColor: Colors.surface, borderRadius: 16, padding: 16, marginBottom: 20, borderWidth: 1, borderColor: Colors.border },
  weekRow:      { flexDirection: 'row', justifyContent: 'space-around', marginTop: 12 },
  weekStat:     { alignItems: 'center' },
  weekVal:      { color: Colors.text, fontWeight: '800', fontSize: 22 },
  weekLbl:      { color: Colors.textMuted, fontSize: 12, marginTop: 2 },
  sectionTitle: { color: Colors.text, fontWeight: '700', fontSize: 16, marginBottom: 12 },
  streakBanner: { flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: Colors.surface, borderRadius: 14, padding: 14, marginBottom: 16, borderWidth: 1, borderColor: Colors.amber + '55' },
  streakEmoji:  { fontSize: 28 },
  streakTitle:  { color: Colors.text, fontWeight: '700', fontSize: 14 },
  streakSub:    { color: Colors.textMuted, fontSize: 12, marginTop: 2 },
  corrCard:  { flexDirection: 'row', gap: 10, backgroundColor: Colors.surface, borderRadius: 12, padding: 14, marginBottom: 8, borderWidth: 1, borderColor: Colors.secondary + '33' },
  corrTitle: { color: Colors.text, fontWeight: '600', fontSize: 13, marginBottom: 4 },
  corrBody:  { color: Colors.textMuted, fontSize: 12, lineHeight: 18 },
});
