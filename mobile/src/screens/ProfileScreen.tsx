import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ScrollView, Alert } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
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

export default function ProfileScreen() {
  const { user, logout } = useAuthStore();
  const navigation = useNavigation<any>();

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
            <MenuItem icon="person-outline"    label="Display Name"   value={user?.display_name ?? '—'} onPress={() => {}} />
            <View style={styles.divider} />
            <MenuItem icon="mail-outline"      label="Email"          value={user?.email}                onPress={() => {}} />
            <View style={styles.divider} />
            <MenuItem icon="time-outline"      label="Timezone"       value={user?.timezone ?? 'UTC'}    onPress={() => {}} />
          </View>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Health & Preferences</Text>
          <View style={styles.card}>
            <MenuItem icon="fitness-outline"    label="Health Profile"   value="Edit"        onPress={() => navigation.navigate('HealthProfile')} />
            <View style={styles.divider} />
            <MenuItem icon="notifications-outline" label="Bedtime Reminder" value="10:30 PM" onPress={() => {}} />
            <View style={styles.divider} />
            <MenuItem icon="shield-checkmark-outline" label="Privacy Mode"  value="Off"      onPress={() => {}} />
          </View>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>App</Text>
          <View style={styles.card}>
            <MenuItem icon="information-circle-outline" label="About SleepSense" onPress={() => {}} />
            <View style={styles.divider} />
            <MenuItem icon="document-text-outline"     label="Privacy Policy"    onPress={() => {}} />
          </View>
        </View>

        <TouchableOpacity style={styles.logoutBtn} onPress={handleLogout}>
          <Ionicons name="log-out-outline" size={18} color={Colors.danger} />
          <Text style={styles.logoutText}>Sign Out</Text>
        </TouchableOpacity>

        <Text style={styles.version}>SleepSense v1.0.0 · Sample Build</Text>
      </ScrollView>
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
});
