import React, { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, StyleSheet, KeyboardAvoidingView, Platform, ScrollView } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { Colors } from '../theme/colors';
import { useAuthStore } from '../store/authStore';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { AuthStackParams } from '../navigation/AuthNavigator';

type Props = { navigation: NativeStackNavigationProp<AuthStackParams, 'Register'> };

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const pwStrength = (pw: string): { level: 0|1|2|3|4; label: string; color: string } => {
  if (!pw) return { level: 0, label: '', color: Colors.border };
  let score = 0;
  if (pw.length >= 8)            score++;
  if (/[A-Z]/.test(pw))         score++;
  if (/[0-9]/.test(pw))         score++;
  if (/[^A-Za-z0-9]/.test(pw)) score++;
  const map = [
    { label: 'Too short', color: Colors.danger },
    { label: 'Weak',      color: Colors.danger },
    { label: 'Fair',      color: Colors.amber },
    { label: 'Good',      color: Colors.good },
    { label: 'Strong',    color: Colors.excellent },
  ];
  return { level: score as 0|1|2|3|4, ...map[score] };
};

export default function RegisterScreen({ navigation }: Props) {
  const [name, setName]           = useState('');
  const [email, setEmail]         = useState('');
  const [password, setPassword]   = useState('');
  const [confirm, setConfirm]     = useState('');
  const [showPw, setShowPw]       = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [loading, setLoading]     = useState(false);
  const [errors, setErrors]       = useState<Record<string, string>>({});
  const { register }              = useAuthStore();

  const strength = pwStrength(password);

  const clearErr = (key: string) =>
    setErrors(prev => { const n = { ...prev }; delete n[key]; return n; });

  const validate = () => {
    const e: Record<string, string> = {};
    if (!name.trim())               e.name     = 'Full name is required';
    if (!email.trim())              e.email    = 'Email is required';
    else if (!EMAIL_RE.test(email)) e.email    = 'Enter a valid email address';
    if (!password)                  e.password = 'Password is required';
    else if (password.length < 6)   e.password = 'At least 6 characters required';
    if (!confirm)                   e.confirm  = 'Please confirm your password';
    else if (confirm !== password)  e.confirm  = 'Passwords do not match';
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleRegister = async () => {
    if (!validate()) return;
    setLoading(true);
    try {
      await register(email.trim().toLowerCase(), password, name.trim());
    } catch (e: any) {
      setErrors({ form: e?.response?.data?.detail ?? 'Something went wrong' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <LinearGradient colors={['#0A1628', '#112240']} style={{ flex: 1 }}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
          <TouchableOpacity onPress={() => navigation.goBack()} style={styles.back}>
            <Ionicons name="arrow-back" size={24} color={Colors.text} />
          </TouchableOpacity>

          <Text style={styles.heading}>Create Account</Text>
          <Text style={styles.sub}>Start tracking your sleep tonight</Text>

          <View style={styles.card}>
            {errors.form && (
              <View style={styles.formError}>
                <Ionicons name="alert-circle-outline" size={16} color={Colors.danger} />
                <Text style={styles.formErrorText}>{errors.form}</Text>
              </View>
            )}

            <Text style={styles.label}>Full Name</Text>
            <View style={[styles.inputWrap, errors.name && styles.inputError]}>
              <Ionicons name="person-outline" size={18} color={errors.name ? Colors.danger : Colors.textMuted} />
              <TextInput
                style={styles.input} placeholder="Your name" placeholderTextColor={Colors.textMuted}
                value={name} onChangeText={t => { setName(t); clearErr('name'); }}
                autoCapitalize="words"
              />
            </View>
            {errors.name && <Text style={styles.errorText}>{errors.name}</Text>}

            <Text style={styles.label}>Email</Text>
            <View style={[styles.inputWrap, errors.email && styles.inputError]}>
              <Ionicons name="mail-outline" size={18} color={errors.email ? Colors.danger : Colors.textMuted} />
              <TextInput
                style={styles.input} placeholder="you@example.com" placeholderTextColor={Colors.textMuted}
                value={email} onChangeText={t => { setEmail(t); clearErr('email'); }}
                autoCapitalize="none" keyboardType="email-address"
              />
            </View>
            {errors.email && <Text style={styles.errorText}>{errors.email}</Text>}

            <Text style={styles.label}>Password</Text>
            <View style={[styles.inputWrap, errors.password && styles.inputError]}>
              <Ionicons name="lock-closed-outline" size={18} color={errors.password ? Colors.danger : Colors.textMuted} />
              <TextInput
                style={styles.input} placeholder="Min. 6 characters" placeholderTextColor={Colors.textMuted}
                value={password} onChangeText={t => { setPassword(t); clearErr('password'); }}
                secureTextEntry={!showPw}
              />
              <TouchableOpacity onPress={() => setShowPw(!showPw)}>
                <Ionicons name={showPw ? 'eye-off-outline' : 'eye-outline'} size={18} color={Colors.textMuted} />
              </TouchableOpacity>
            </View>
            {password.length > 0 && (
              <View style={styles.strengthWrap}>
                <View style={styles.strengthBar}>
                  {[1, 2, 3, 4].map(i => (
                    <View key={i} style={[styles.strengthSeg, { backgroundColor: i <= strength.level ? strength.color : Colors.border }]} />
                  ))}
                </View>
                <Text style={[styles.strengthLabel, { color: strength.color }]}>{strength.label}</Text>
              </View>
            )}
            {errors.password && <Text style={styles.errorText}>{errors.password}</Text>}

            <Text style={styles.label}>Confirm Password</Text>
            <View style={[styles.inputWrap, errors.confirm && styles.inputError]}>
              <Ionicons name="lock-closed-outline" size={18} color={errors.confirm ? Colors.danger : Colors.textMuted} />
              <TextInput
                style={styles.input} placeholder="Re-enter password" placeholderTextColor={Colors.textMuted}
                value={confirm} onChangeText={t => { setConfirm(t); clearErr('confirm'); }}
                secureTextEntry={!showConfirm}
              />
              <TouchableOpacity onPress={() => setShowConfirm(!showConfirm)}>
                <Ionicons name={showConfirm ? 'eye-off-outline' : 'eye-outline'} size={18} color={Colors.textMuted} />
              </TouchableOpacity>
            </View>
            {errors.confirm && <Text style={styles.errorText}>{errors.confirm}</Text>}

            <TouchableOpacity style={styles.btn} onPress={handleRegister} disabled={loading}>
              <LinearGradient colors={[Colors.primary, Colors.primaryDark]} style={styles.btnInner}>
                <Text style={styles.btnText}>{loading ? 'Creating account…' : 'Create Account'}</Text>
              </LinearGradient>
            </TouchableOpacity>

            <TouchableOpacity onPress={() => navigation.navigate('Login')} style={styles.switchRow}>
              <Text style={styles.switchText}>Already have an account? </Text>
              <Text style={[styles.switchText, { color: Colors.primary }]}>Sign in</Text>
            </TouchableOpacity>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  container:     { flexGrow: 1, paddingHorizontal: 24, paddingTop: 60, paddingBottom: 40 },
  back:          { marginBottom: 24 },
  heading:       { fontSize: 28, fontWeight: '800', color: Colors.text },
  sub:           { color: Colors.textSub, marginTop: 6, marginBottom: 28 },
  card:          { backgroundColor: Colors.surface, borderRadius: 20, padding: 24 },
  formError:     { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: Colors.danger + '18', borderRadius: 10, padding: 12, marginBottom: 12 },
  formErrorText: { color: Colors.danger, fontSize: 13, flex: 1 },
  label:         { color: Colors.textSub, fontSize: 13, marginBottom: 6, marginTop: 16 },
  inputWrap:     { flexDirection: 'row', alignItems: 'center', backgroundColor: Colors.bg, borderRadius: 12, borderWidth: 1, borderColor: Colors.border, paddingHorizontal: 14, paddingVertical: 12, gap: 10 },
  inputError:    { borderColor: Colors.danger },
  input:         { flex: 1, color: Colors.text, fontSize: 15 },
  errorText:     { color: Colors.danger, fontSize: 12, marginTop: 4, marginLeft: 2 },
  strengthWrap:  { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 8 },
  strengthBar:   { flex: 1, flexDirection: 'row', gap: 4 },
  strengthSeg:   { flex: 1, height: 4, borderRadius: 2 },
  strengthLabel: { fontSize: 12, fontWeight: '600', minWidth: 50, textAlign: 'right' },
  btn:           { borderRadius: 12, overflow: 'hidden', marginTop: 24 },
  btnInner:      { paddingVertical: 15, alignItems: 'center' },
  btnText:       { color: '#fff', fontWeight: '700', fontSize: 16 },
  switchRow:     { flexDirection: 'row', justifyContent: 'center', marginTop: 20 },
  switchText:    { color: Colors.textSub, fontSize: 14 },
});
