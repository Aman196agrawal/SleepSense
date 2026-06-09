import React, { useState, useEffect } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, ScrollView,
  Alert, Modal, ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Gradients, Radii } from '../theme';
import AuroraBackground from '../components/AuroraBackground';
import { useAuthStore } from '../store/authStore';
import { useNavigation } from '@react-navigation/native';
import type { ProfileStackNav } from '../navigation/MainNavigator';
import { scheduleBedtimeReminder } from '../api/notifications';

const MenuItem = ({ icon, label, value, onPress }: any) => (
  <TouchableOpacity style={styles.menuItem} onPress={onPress}>
    <View style={styles.menuLeft}>
      <View style={styles.menuIcon}>
        <Ionicons name={icon} size={18} color={Colors.primary} />
      </View>
      <Text style={styles.menuLabel}>{label}</Text>
    </View>
    <View style={styles.menuRight}>
      {value && <Text style={styles.menuValue}>{value}</Text>}
      <Ionicons name="chevron-forward" size={16} color={Colors.textMuted} />
    </View>
  </TouchableOpacity>
);

function parse24h(hhmm: string): { h: number; m: number; ap: 'AM' | 'PM' } {
  const [hStr, mStr] = hhmm.split(':');
  const h24 = parseInt(hStr, 10);
  const m   = parseInt(mStr, 10);
  return {
    h:  h24 % 12 || 12,
    m,
    ap: h24 >= 12 ? 'PM' : 'AM',
  };
}

function to24h(h: number, m: number, ap: 'AM' | 'PM'): string {
  const h24 = ap === 'PM' ? (h === 12 ? 12 : h + 12) : (h === 12 ? 0 : h);
  return `${String(h24).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
}

function displayTime(hhmm: string): string {
  const { h, m, ap } = parse24h(hhmm);
  return `${h}:${String(m).padStart(2, '0')} ${ap}`;
}

export default function ProfileScreen() {
  const { user, logout, updateProfile } = useAuthStore();
  const navigation = useNavigation<ProfileStackNav>();

  const [showPicker, setShowPicker]     = useState(false);
  const [pickerH, setPickerH]           = useState(10);
  const [pickerM, setPickerM]           = useState(30);
  const [pickerAP, setPickerAP]         = useState<'AM' | 'PM'>('PM');
  const [saving, setSaving]             = useState(false);

  useEffect(() => {
    if (user?.bedtime_reminder_time) {
      const { h, m, ap } = parse24h(user.bedtime_reminder_time);
      setPickerH(h);
      setPickerM(m);
      setPickerAP(ap);
    }
  }, [user?.bedtime_reminder_time]);

  const reminderValue = user?.bedtime_reminder_time
    ? displayTime(user.bedtime_reminder_time)
    : '—';

  const handleSave = async () => {
    setSaving(true);
    try {
      const hhmm = to24h(pickerH, pickerM, pickerAP);
      await updateProfile({ bedtime_reminder_time: hhmm });
      await scheduleBedtimeReminder(hhmm);
      setShowPicker(false);
    } catch {
      Alert.alert('Error', 'Could not save reminder time. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const handleEditDisplayName = () =>
    Alert.alert('Display Name', 'Display name editing is coming in the next release.', [{ text: 'OK' }]);

  const handleEditEmail = () =>
    Alert.alert('Email', 'Email changes require verification and are coming in the next release.', [{ text: 'OK' }]);

  const handleEditTimezone = () =>
    Alert.alert('Timezone', 'Timezone selection is coming in the next release.', [{ text: 'OK' }]);

  const handlePrivacyMode = () =>
    Alert.alert('Privacy Mode', 'Toggle Privacy Mode on the Record screen before starting a session to keep audio on-device.', [{ text: 'Got it' }]);

  const handleAbout = () =>
    Alert.alert('SleepSense', 'Version 1.0.0 — Sample Build\n\nA sleep & snoring analytics platform built with React Native + FastAPI.', [{ text: 'OK' }]);

  const handlePrivacyPolicy = () =>
    Alert.alert('Privacy Policy', 'Full privacy policy will be available at sleepsense.app/privacy before public launch.', [{ text: 'OK' }]);

  const handleLogout = () => {
    Alert.alert('Sign Out', 'Are you sure you want to sign out?', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Sign Out', style: 'destructive', onPress: logout },
    ]);
  };

  const initial = (user?.display_name ?? user?.email ?? 'U')[0].toUpperCase();

  return (
    <AuroraBackground style={{ flex: 1 }}>
    <SafeAreaView style={{ flex: 1 }} edges={['top']}>
      <ScrollView contentContainerStyle={styles.container} showsVerticalScrollIndicator={false}>
        <Text style={styles.heading}>Profile</Text>

        {/* Avatar */}
        <View style={styles.avatarSection}>
          <LinearGradient
            colors={Gradients.cta as any}
            start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
            style={styles.avatar}
          >
            <View style={styles.avatarInner}>
              <Text style={styles.avatarText}>{initial}</Text>
            </View>
          </LinearGradient>
          <Text style={styles.displayName}>{user?.display_name ?? 'Sleeper'}</Text>
          <Text style={styles.email}>{user?.email}</Text>
        </View>

        {/* Settings sections */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Account</Text>
          <View style={styles.card}>
            <MenuItem icon="person-outline" label="Display Name" value={user?.display_name ?? '—'} onPress={handleEditDisplayName} />
            <View style={styles.divider} />
            <MenuItem icon="mail-outline"   label="Email"        value={user?.email}                onPress={handleEditEmail} />
            <View style={styles.divider} />
            <MenuItem icon="time-outline"   label="Timezone"     value={user?.timezone ?? 'UTC'}    onPress={handleEditTimezone} />
          </View>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Health & Preferences</Text>
          <View style={styles.card}>
            <MenuItem icon="fitness-outline"           label="Health Profile"   value="Edit"         onPress={() => navigation.navigate('HealthProfile')} />
            <View style={styles.divider} />
            <MenuItem icon="flag-outline"              label="Sleep Goals"      value="Manage"       onPress={() => navigation.navigate('Goals')} />
            <View style={styles.divider} />
            <MenuItem
              icon="notifications-outline"
              label="Bedtime Reminder"
              value={reminderValue}
              onPress={() => setShowPicker(true)}
            />
            <View style={styles.divider} />
            <MenuItem icon="shield-checkmark-outline" label="Privacy Mode"     value="Off"          onPress={handlePrivacyMode} />
          </View>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>App</Text>
          <View style={styles.card}>
            <MenuItem icon="information-circle-outline" label="About SleepSense" onPress={handleAbout} />
            <View style={styles.divider} />
            <MenuItem icon="document-text-outline"      label="Privacy Policy"   onPress={handlePrivacyPolicy} />
          </View>
        </View>

        <TouchableOpacity style={styles.logoutBtn} onPress={handleLogout}>
          <Ionicons name="log-out-outline" size={18} color={Colors.danger} />
          <Text style={styles.logoutText}>Sign Out</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.logoutBtn, { borderColor: Colors.danger + '22', marginTop: 8 }]}
          onPress={() => {
            Alert.alert(
              'Delete Account',
              'This permanently deletes your account and all sleep data. This cannot be undone.',
              [
                { text: 'Cancel', style: 'cancel' },
                {
                  text: 'Delete Account',
                  style: 'destructive',
                  onPress: async () => {
                    try {
                      const { deleteAccount } = await import('../api/auth.api');
                      await deleteAccount();
                      logout();
                    } catch {
                      Alert.alert('Error', 'Could not delete account. Please try again.');
                    }
                  },
                },
              ]
            );
          }}
        >
          <Ionicons name="trash-outline" size={18} color={Colors.danger + 'AA'} />
          <Text style={[styles.logoutText, { color: Colors.danger + 'AA', fontSize: 13 }]}>Delete Account</Text>
        </TouchableOpacity>

        <Text style={styles.version}>SleepSense v1.0.0 · Sample Build</Text>
      </ScrollView>

      {/* Bedtime reminder time picker */}
      <Modal visible={showPicker} transparent animationType="fade">
        <TouchableOpacity
          style={styles.overlay}
          activeOpacity={1}
          onPress={() => setShowPicker(false)}
        >
          <View style={styles.pickerCard} onStartShouldSetResponder={() => true}>
            <Text style={styles.pickerTitle}>Bedtime Reminder</Text>

            <View style={styles.pickerRow}>
              {/* Hour */}
              <View style={styles.pickerCol}>
                <TouchableOpacity onPress={() => setPickerH(h => h === 12 ? 1 : h + 1)} hitSlop={{ top: 8, bottom: 8, left: 12, right: 12 }}>
                  <Ionicons name="chevron-up" size={24} color={Colors.primary} />
                </TouchableOpacity>
                <Text style={styles.pickerVal}>{String(pickerH).padStart(2, '0')}</Text>
                <TouchableOpacity onPress={() => setPickerH(h => h === 1 ? 12 : h - 1)} hitSlop={{ top: 8, bottom: 8, left: 12, right: 12 }}>
                  <Ionicons name="chevron-down" size={24} color={Colors.primary} />
                </TouchableOpacity>
              </View>

              <Text style={styles.pickerColon}>:</Text>

              {/* Minute (5-minute steps) */}
              <View style={styles.pickerCol}>
                <TouchableOpacity onPress={() => setPickerM(m => (m + 5) % 60)} hitSlop={{ top: 8, bottom: 8, left: 12, right: 12 }}>
                  <Ionicons name="chevron-up" size={24} color={Colors.primary} />
                </TouchableOpacity>
                <Text style={styles.pickerVal}>{String(pickerM).padStart(2, '0')}</Text>
                <TouchableOpacity onPress={() => setPickerM(m => m === 0 ? 55 : m - 5)} hitSlop={{ top: 8, bottom: 8, left: 12, right: 12 }}>
                  <Ionicons name="chevron-down" size={24} color={Colors.primary} />
                </TouchableOpacity>
              </View>

              {/* AM / PM */}
              <View style={styles.pickerCol}>
                <TouchableOpacity onPress={() => setPickerAP(ap => ap === 'AM' ? 'PM' : 'AM')} hitSlop={{ top: 8, bottom: 8, left: 12, right: 12 }}>
                  <Ionicons name="chevron-up" size={24} color={Colors.primary} />
                </TouchableOpacity>
                <Text style={[styles.pickerVal, { fontSize: 20 }]}>{pickerAP}</Text>
                <TouchableOpacity onPress={() => setPickerAP(ap => ap === 'AM' ? 'PM' : 'AM')} hitSlop={{ top: 8, bottom: 8, left: 12, right: 12 }}>
                  <Ionicons name="chevron-down" size={24} color={Colors.primary} />
                </TouchableOpacity>
              </View>
            </View>

            <TouchableOpacity style={styles.saveBtn} onPress={handleSave} disabled={saving}>
              <LinearGradient colors={Gradients.cta as any} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} style={styles.saveBtnInner}>
                {saving
                  ? <ActivityIndicator size="small" color="#fff" />
                  : <Text style={styles.saveBtnText}>Save</Text>
                }
              </LinearGradient>
            </TouchableOpacity>
          </View>
        </TouchableOpacity>
      </Modal>
    </SafeAreaView>
    </AuroraBackground>
  );
}

const styles = StyleSheet.create({
  container:    { padding: 20, paddingBottom: 120 },
  heading:      { color: Colors.text, fontSize: 28, fontWeight: '800', marginBottom: 24, letterSpacing: -0.8 },
  avatarSection:{ alignItems: 'center', marginBottom: 32 },
  avatar:       { width: 88, height: 88, borderRadius: 44, alignItems: 'center', justifyContent: 'center', padding: 3, shadowColor: '#A78BFA', shadowOpacity: 0.5, shadowRadius: 20, shadowOffset: { width: 0, height: 0 }, elevation: 10 },
  avatarInner:  { width: '100%', height: '100%', borderRadius: 42, backgroundColor: Colors.bg, alignItems: 'center', justifyContent: 'center' },
  avatarText:   { color: Colors.text, fontSize: 32, fontWeight: '800', letterSpacing: -0.4 },
  displayName:  { color: Colors.text, fontSize: 22, fontWeight: '800', marginTop: 14, letterSpacing: -0.4 },
  email:        { color: Colors.textSub, fontSize: 13, marginTop: 4 },
  section:      { marginBottom: 20 },
  sectionTitle: { color: Colors.textMuted, fontSize: 11, fontWeight: '700', letterSpacing: 1.4, textTransform: 'uppercase', marginBottom: 10, marginLeft: 4 },
  card:         { backgroundColor: 'rgba(31,31,61,0.6)', borderRadius: Radii.lg, borderWidth: 1, borderColor: Colors.borderSoft, overflow: 'hidden' },
  menuItem:     { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', padding: 14 },
  menuLeft:     { flexDirection: 'row', alignItems: 'center', gap: 12 },
  menuIcon:     { width: 34, height: 34, borderRadius: 10, backgroundColor: Colors.primary + '22', alignItems: 'center', justifyContent: 'center' },
  menuLabel:    { color: Colors.text, fontSize: 14, fontWeight: '600' },
  menuRight:    { flexDirection: 'row', alignItems: 'center', gap: 6 },
  menuValue:    { color: Colors.textMuted, fontSize: 13, fontWeight: '500' },
  divider:      { height: 1, backgroundColor: Colors.borderSoft, marginLeft: 60 },
  logoutBtn:    { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, padding: 14, borderRadius: Radii.lg, borderWidth: 1, borderColor: Colors.danger + '44', marginTop: 8 },
  logoutText:   { color: Colors.danger, fontWeight: '700', fontSize: 14, letterSpacing: 0.2 },
  version:      { textAlign: 'center', color: Colors.textMuted, fontSize: 12, marginTop: 24, fontWeight: '500' },
  // Modal
  overlay:      { flex: 1, backgroundColor: 'rgba(0,0,0,0.7)', justifyContent: 'center', alignItems: 'center' },
  pickerCard:   { backgroundColor: Colors.surface, borderRadius: Radii.xxl, padding: 28, width: '85%', alignItems: 'center', borderWidth: 1, borderColor: Colors.borderSoft },
  pickerTitle:  { color: Colors.text, fontSize: 17, fontWeight: '800', marginBottom: 28, letterSpacing: -0.2 },
  pickerRow:    { flexDirection: 'row', alignItems: 'center', gap: 12, marginBottom: 28 },
  pickerCol:    { alignItems: 'center', gap: 14 },
  pickerColon:  { color: Colors.text, fontSize: 30, fontWeight: '700', marginBottom: 4 },
  pickerVal:    { color: Colors.text, fontSize: 30, fontWeight: '800', minWidth: 54, textAlign: 'center', letterSpacing: -0.6 },
  saveBtn:      { borderRadius: Radii.lg, overflow: 'hidden', width: '100%' },
  saveBtnInner: { paddingVertical: 14, alignItems: 'center' },
  saveBtnText:  { color: '#fff', fontWeight: '800', fontSize: 16, letterSpacing: 0.2 },
});
