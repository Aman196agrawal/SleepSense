import React, { useState, useEffect } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, ScrollView,
  Alert, Modal, ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { Colors } from '../theme/colors';
import { useAuthStore } from '../store/authStore';
import { useNavigation } from '@react-navigation/native';

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
  const navigation = useNavigation<any>();

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
      await updateProfile({ bedtime_reminder_time: to24h(pickerH, pickerM, pickerAP) });
      setShowPicker(false);
    } catch {
      Alert.alert('Error', 'Could not save reminder time. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const handleLogout = () => {
    Alert.alert('Sign Out', 'Are you sure you want to sign out?', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Sign Out', style: 'destructive', onPress: logout },
    ]);
  };

  const initial = (user?.display_name ?? user?.email ?? 'U')[0].toUpperCase();

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.bg }}>
      <ScrollView contentContainerStyle={styles.container}>
        <Text style={styles.heading}>Profile</Text>

        {/* Avatar */}
        <View style={styles.avatarSection}>
          <View style={styles.avatar}>
            <Text style={styles.avatarText}>{initial}</Text>
          </View>
          <Text style={styles.displayName}>{user?.display_name ?? 'Sleeper'}</Text>
          <Text style={styles.email}>{user?.email}</Text>
        </View>

        {/* Settings sections */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Account</Text>
          <View style={styles.card}>
            <MenuItem icon="person-outline" label="Display Name" value={user?.display_name ?? '—'} onPress={() => {}} />
            <View style={styles.divider} />
            <MenuItem icon="mail-outline"   label="Email"        value={user?.email}                onPress={() => {}} />
            <View style={styles.divider} />
            <MenuItem icon="time-outline"   label="Timezone"     value={user?.timezone ?? 'UTC'}    onPress={() => {}} />
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
            <MenuItem icon="shield-checkmark-outline" label="Privacy Mode"     value="Off"          onPress={() => {}} />
          </View>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>App</Text>
          <View style={styles.card}>
            <MenuItem icon="information-circle-outline" label="About SleepSense" onPress={() => {}} />
            <View style={styles.divider} />
            <MenuItem icon="document-text-outline"      label="Privacy Policy"   onPress={() => {}} />
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
              <LinearGradient colors={[Colors.primary, Colors.primaryDark]} style={styles.saveBtnInner}>
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
  );
}

const styles = StyleSheet.create({
  container:    { padding: 20, paddingBottom: 40 },
  heading:      { color: Colors.text, fontSize: 22, fontWeight: '700', marginBottom: 24 },
  avatarSection:{ alignItems: 'center', marginBottom: 32 },
  avatar:       { width: 80, height: 80, borderRadius: 40, backgroundColor: Colors.surfaceHigh, alignItems: 'center', justifyContent: 'center', borderWidth: 2, borderColor: Colors.primary },
  avatarText:   { color: Colors.primary, fontSize: 32, fontWeight: '800' },
  displayName:  { color: Colors.text, fontSize: 20, fontWeight: '700', marginTop: 12 },
  email:        { color: Colors.textSub, fontSize: 14, marginTop: 4 },
  section:      { marginBottom: 20 },
  sectionTitle: { color: Colors.textMuted, fontSize: 12, fontWeight: '600', letterSpacing: 0.8, textTransform: 'uppercase', marginBottom: 8, marginLeft: 4 },
  card:         { backgroundColor: Colors.surface, borderRadius: 14, borderWidth: 1, borderColor: Colors.border },
  menuItem:     { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', padding: 14 },
  menuLeft:     { flexDirection: 'row', alignItems: 'center', gap: 12 },
  menuIcon:     { width: 32, height: 32, borderRadius: 8, backgroundColor: Colors.surfaceHigh, alignItems: 'center', justifyContent: 'center' },
  menuLabel:    { color: Colors.text, fontSize: 14 },
  menuRight:    { flexDirection: 'row', alignItems: 'center', gap: 6 },
  menuValue:    { color: Colors.textMuted, fontSize: 13 },
  divider:      { height: 1, backgroundColor: Colors.border, marginLeft: 58 },
  logoutBtn:    { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, padding: 16, borderRadius: 14, borderWidth: 1, borderColor: Colors.danger + '44', marginTop: 8 },
  logoutText:   { color: Colors.danger, fontWeight: '600', fontSize: 15 },
  version:      { textAlign: 'center', color: Colors.textMuted, fontSize: 12, marginTop: 24 },
  // Modal
  overlay:      { flex: 1, backgroundColor: 'rgba(0,0,0,0.6)', justifyContent: 'center', alignItems: 'center' },
  pickerCard:   { backgroundColor: Colors.surface, borderRadius: 20, padding: 28, width: '80%', alignItems: 'center' },
  pickerTitle:  { color: Colors.text, fontSize: 17, fontWeight: '700', marginBottom: 28 },
  pickerRow:    { flexDirection: 'row', alignItems: 'center', gap: 12, marginBottom: 28 },
  pickerCol:    { alignItems: 'center', gap: 14 },
  pickerColon:  { color: Colors.text, fontSize: 30, fontWeight: '700', marginBottom: 4 },
  pickerVal:    { color: Colors.text, fontSize: 30, fontWeight: '700', minWidth: 54, textAlign: 'center' },
  saveBtn:      { borderRadius: 12, overflow: 'hidden', width: '100%' },
  saveBtnInner: { paddingVertical: 14, alignItems: 'center' },
  saveBtnText:  { color: '#fff', fontWeight: '700', fontSize: 16 },
});
