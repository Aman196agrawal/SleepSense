import React, { useState, useRef } from 'react';
import { View, Text, TextInput, TouchableOpacity, StyleSheet, KeyboardAvoidingView, Platform, ScrollView } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Gradients, Radii } from '../theme';
import AuroraBackground from '../components/AuroraBackground';
import { useAuthStore } from '../store/authStore';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { AuthStackParams } from '../navigation/AuthNavigator';

type Props = { navigation: NativeStackNavigationProp<AuthStackParams, 'ResetPassword'> };

export default function ResetPasswordScreen({ navigation }: Props) {
  const [token, setToken]       = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm]   = useState('');
  const [showPw, setShowPw]         = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [loading, setLoading]       = useState(false);
  const pwRef      = useRef<TextInput>(null);
  const confirmRef = useRef<TextInput>(null);
  const [done, setDone]         = useState(false);
  const [errors, setErrors]     = useState<Record<string, string>>({});
  const { resetPassword }       = useAuthStore();

  const validate = () => {
    const e: Record<string, string> = {};
    if (!token.trim())              e.token    = 'Paste the reset token from your email';
    if (!password)                  e.password = 'New password is required';
    else if (password.length < 6)   e.password = 'At least 6 characters required';
    if (confirm !== password)       e.confirm  = 'Passwords do not match';
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleReset = async () => {
    if (!validate()) return;
    setLoading(true);
    try {
      await resetPassword(token.trim(), password);
      setDone(true);
    } catch (e: any) {
      setErrors({ form: e?.response?.data?.detail ?? 'Invalid or expired token' });
    } finally {
      setLoading(false);
    }
  };

  if (done) {
    return (
      <AuroraBackground style={{ flex: 1 }}>
        <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24 }}>
          <View style={styles.successCard}>
            <Ionicons name="checkmark-circle" size={56} color={Colors.excellent} />
            <Text style={styles.successTitle}>Password Updated!</Text>
            <Text style={styles.successBody}>Your password has been changed. You can now sign in with your new password.</Text>
            <TouchableOpacity style={styles.btn} onPress={() => navigation.navigate('Login')}>
              <LinearGradient colors={Gradients.cta as any} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} style={styles.btnInner}>
                <Text style={styles.btnText}>Back to Sign In</Text>
              </LinearGradient>
            </TouchableOpacity>
          </View>
        </View>
      </AuroraBackground>
    );
  }

  return (
    <AuroraBackground style={{ flex: 1 }}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">

          <TouchableOpacity onPress={() => navigation.goBack()} style={styles.back}>
            <Ionicons name="arrow-back" size={24} color={Colors.text} />
          </TouchableOpacity>

          <Text style={styles.heading}>Reset Password</Text>
          <Text style={styles.sub}>Paste the token from your reset email, then choose a new password.</Text>

          <View style={styles.card}>
            {errors.form && (
              <View style={styles.errBox}>
                <Ionicons name="alert-circle-outline" size={16} color={Colors.danger} />
                <Text style={styles.errText}>{errors.form}</Text>
              </View>
            )}

            <Text style={styles.label}>Reset Token</Text>
            <View style={[styles.inputWrap, errors.token && styles.inputError]}>
              <Ionicons name="key-outline" size={18} color={errors.token ? Colors.danger : Colors.textMuted} />
              <TextInput
                style={styles.input}
                placeholder="Paste token from email"
                placeholderTextColor={Colors.textMuted}
                value={token}
                onChangeText={t => { setToken(t); setErrors(p => ({ ...p, token: '' })); }}
                autoCapitalize="none"
                autoCorrect={false}
                returnKeyType="next"
                blurOnSubmit={false}
                onSubmitEditing={() => pwRef.current?.focus()}
              />
            </View>
            {errors.token && <Text style={styles.errInline}>{errors.token}</Text>}

            <Text style={styles.label}>New Password</Text>
            <View style={[styles.inputWrap, errors.password && styles.inputError]}>
              <Ionicons name="lock-closed-outline" size={18} color={errors.password ? Colors.danger : Colors.textMuted} />
              <TextInput
                ref={pwRef}
                style={styles.input}
                placeholder="Min. 6 characters"
                placeholderTextColor={Colors.textMuted}
                value={password}
                onChangeText={t => { setPassword(t); setErrors(p => ({ ...p, password: '' })); }}
                secureTextEntry={!showPw}
                returnKeyType="next"
                blurOnSubmit={false}
                onSubmitEditing={() => confirmRef.current?.focus()}
              />
              <TouchableOpacity onPress={() => setShowPw(!showPw)}>
                <Ionicons name={showPw ? 'eye-off-outline' : 'eye-outline'} size={18} color={Colors.textMuted} />
              </TouchableOpacity>
            </View>
            {errors.password && <Text style={styles.errInline}>{errors.password}</Text>}

            <Text style={styles.label}>Confirm New Password</Text>
            <View style={[styles.inputWrap, errors.confirm && styles.inputError]}>
              <Ionicons name="lock-closed-outline" size={18} color={errors.confirm ? Colors.danger : Colors.textMuted} />
              <TextInput
                ref={confirmRef}
                style={styles.input}
                placeholder="Re-enter new password"
                placeholderTextColor={Colors.textMuted}
                value={confirm}
                onChangeText={t => { setConfirm(t); setErrors(p => ({ ...p, confirm: '' })); }}
                secureTextEntry={!showConfirm}
                returnKeyType="done"
                onSubmitEditing={handleReset}
              />
              <TouchableOpacity onPress={() => setShowConfirm(!showConfirm)}>
                <Ionicons name={showConfirm ? 'eye-off-outline' : 'eye-outline'} size={18} color={Colors.textMuted} />
              </TouchableOpacity>
            </View>
            {errors.confirm && <Text style={styles.errInline}>{errors.confirm}</Text>}

            <TouchableOpacity style={styles.btn} onPress={handleReset} disabled={loading}>
              <LinearGradient colors={Gradients.cta as any} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} style={styles.btnInner}>
                <Text style={styles.btnText}>{loading ? 'Updating…' : 'Set New Password'}</Text>
              </LinearGradient>
            </TouchableOpacity>

            <TouchableOpacity onPress={() => navigation.navigate('Login')} style={styles.switchRow}>
              <Text style={styles.switchText}>Back to </Text>
              <Text style={[styles.switchText, { color: Colors.primary }]}>Sign In</Text>
            </TouchableOpacity>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </AuroraBackground>
  );
}

const styles = StyleSheet.create({
  container:    { flexGrow: 1, paddingHorizontal: 24, paddingTop: 60, paddingBottom: 40 },
  back:         { marginBottom: 24 },
  heading:      { fontSize: 26, fontWeight: '800', color: Colors.text },
  sub:          { color: Colors.textSub, marginTop: 8, marginBottom: 28, lineHeight: 20 },
  card:         { backgroundColor: 'rgba(31,31,61,0.7)', borderRadius: Radii.xxl, padding: 24, borderWidth: 1, borderColor: Colors.borderSoft },
  errBox:       { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: Colors.danger + '18', borderRadius: 10, padding: 12, marginBottom: 12 },
  errText:      { color: Colors.danger, fontSize: 13, flex: 1 },
  errInline:    { color: Colors.danger, fontSize: 12, marginTop: 4, marginLeft: 2 },
  label:        { color: Colors.textSub, fontSize: 13, marginBottom: 6, marginTop: 16 },
  inputWrap:    { flexDirection: 'row', alignItems: 'center', backgroundColor: 'rgba(11,11,31,0.6)', borderRadius: Radii.md, borderWidth: 1, borderColor: Colors.border, paddingHorizontal: 14, paddingVertical: 12, gap: 10 },
  inputError:   { borderColor: Colors.danger },
  input:        { flex: 1, color: Colors.text, fontSize: 15 },
  btn:          { borderRadius: Radii.lg, overflow: 'hidden', marginTop: 24, shadowColor: '#A78BFA', shadowOpacity: 0.5, shadowRadius: 18, shadowOffset: { width: 0, height: 0 }, elevation: 10 },
  btnInner:     { paddingVertical: 15, alignItems: 'center' },
  btnText:      { color: '#fff', fontWeight: '700', fontSize: 16 },
  switchRow:    { flexDirection: 'row', justifyContent: 'center', marginTop: 20 },
  switchText:   { color: Colors.textSub, fontSize: 14 },
  successCard:  { backgroundColor: Colors.surface, borderRadius: 20, padding: 28, alignItems: 'center', width: '100%' },
  successTitle: { color: Colors.text, fontSize: 22, fontWeight: '700', marginTop: 16, marginBottom: 12 },
  successBody:  { color: Colors.textSub, textAlign: 'center', lineHeight: 22, marginBottom: 8 },
});
