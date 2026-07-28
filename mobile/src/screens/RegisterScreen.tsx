import React, { useState, useRef } from 'react';
import { View, Text, TextInput, TouchableOpacity, StyleSheet, KeyboardAvoidingView, Platform, ScrollView, Vibration } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Gradients, Radii } from '../theme';
import AuroraBackground from '../components/AuroraBackground';
import { useAuthStore } from '../store/authStore';
import { apiErrorMessage } from '../api/errors';
import {
  validatePassword, passwordStrength, unmetRules,
  PASSWORD_PLACEHOLDER, PASSWORD_POLICY_HINT,
} from '../utils/password';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { AuthStackParams } from '../navigation/AuthNavigator';

type Props = { navigation: NativeStackNavigationProp<AuthStackParams, 'Register'> };

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// Colour ramp for the 0-4 strength meter. Only level 4 clears the server's
// policy, so nothing below it gets a "passing" colour.
const STRENGTH_COLORS = [
  Colors.border,
  Colors.danger,
  Colors.danger,
  Colors.amber,
  Colors.excellent,
];

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
  const emailRef    = useRef<TextInput>(null);
  const passwordRef = useRef<TextInput>(null);
  const confirmRef  = useRef<TextInput>(null);

  const strength = passwordStrength(password);
  const strengthColor = STRENGTH_COLORS[strength.level];
  const missing = unmetRules(password);

  const clearErr = (key: string) =>
    setErrors(prev => { const n = { ...prev }; delete n[key]; return n; });

  const validate = () => {
    const e: Record<string, string> = {};
    if (!name.trim())               e.name     = 'Full name is required';
    if (!email.trim())              e.email    = 'Email is required';
    else if (!EMAIL_RE.test(email)) e.email    = 'Enter a valid email address';
    const pwError = validatePassword(password);
    if (pwError)                    e.password = pwError;
    if (!confirm)                   e.confirm  = 'Please confirm your password';
    else if (confirm !== password)  e.confirm  = 'Passwords do not match';
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleRegister = async () => {
    if (!validate()) return;
    Vibration.vibrate(15);
    setLoading(true);
    try {
      await register(email.trim().toLowerCase(), password, name.trim());
    } catch (e: any) {
      setErrors({ form: apiErrorMessage(e) });
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuroraBackground style={{ flex: 1 }}>
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
                returnKeyType="next"
                blurOnSubmit={false}
                onSubmitEditing={() => emailRef.current?.focus()}
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
                ref={emailRef}
                returnKeyType="next"
                blurOnSubmit={false}
                onSubmitEditing={() => passwordRef.current?.focus()}
              />
            </View>
            {errors.email && <Text style={styles.errorText}>{errors.email}</Text>}

            <Text style={styles.label}>Password</Text>
            <View style={[styles.inputWrap, errors.password && styles.inputError]}>
              <Ionicons name="lock-closed-outline" size={18} color={errors.password ? Colors.danger : Colors.textMuted} />
              <TextInput
                style={styles.input} placeholder={PASSWORD_PLACEHOLDER} placeholderTextColor={Colors.textMuted}
                value={password} onChangeText={t => { setPassword(t); clearErr('password'); }}
                secureTextEntry={!showPw}
                ref={passwordRef}
                returnKeyType="next"
                blurOnSubmit={false}
                onSubmitEditing={() => confirmRef.current?.focus()}
              />
              <TouchableOpacity onPress={() => setShowPw(!showPw)}>
                <Ionicons name={showPw ? 'eye-off-outline' : 'eye-outline'} size={18} color={Colors.textMuted} />
              </TouchableOpacity>
            </View>
            {password.length === 0 ? (
              <Text style={styles.strengthHint}>{PASSWORD_POLICY_HINT}</Text>
            ) : (
              <>
                <View style={styles.strengthWrap}>
                  <View style={styles.strengthBar}>
                    {[1, 2, 3, 4].map(i => (
                      <View key={i} style={[styles.strengthSeg, { backgroundColor: i <= strength.level ? strengthColor : Colors.border }]} />
                    ))}
                  </View>
                  <Text style={[styles.strengthLabel, { color: strengthColor }]}>{strength.label}</Text>
                </View>
                {missing.length > 0 && (
                  <Text style={styles.strengthHint}>
                    Still needs: {missing.map(r => r.label.toLowerCase()).join(', ')}
                  </Text>
                )}
              </>
            )}
            {errors.password && <Text style={styles.errorText}>{errors.password}</Text>}

            <Text style={styles.label}>Confirm Password</Text>
            <View style={[styles.inputWrap, errors.confirm && styles.inputError]}>
              <Ionicons name="lock-closed-outline" size={18} color={errors.confirm ? Colors.danger : Colors.textMuted} />
              <TextInput
                style={styles.input} placeholder="Re-enter password" placeholderTextColor={Colors.textMuted}
                value={confirm} onChangeText={t => { setConfirm(t); clearErr('confirm'); }}
                secureTextEntry={!showConfirm}
                ref={confirmRef}
                returnKeyType="done"
                onSubmitEditing={handleRegister}
              />
              <TouchableOpacity onPress={() => setShowConfirm(!showConfirm)}>
                <Ionicons name={showConfirm ? 'eye-off-outline' : 'eye-outline'} size={18} color={Colors.textMuted} />
              </TouchableOpacity>
            </View>
            {errors.confirm && <Text style={styles.errorText}>{errors.confirm}</Text>}

            <TouchableOpacity style={styles.btn} onPress={handleRegister} disabled={loading}>
              <LinearGradient colors={Gradients.cta as any} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} style={styles.btnInner}>
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
    </AuroraBackground>
  );
}

const styles = StyleSheet.create({
  container:     { flexGrow: 1, paddingHorizontal: 24, paddingTop: 60, paddingBottom: 40 },
  back:          { marginBottom: 24 },
  heading:       { fontSize: 28, fontWeight: '800', color: Colors.text },
  sub:           { color: Colors.textSub, marginTop: 6, marginBottom: 28 },
  card:          { backgroundColor: 'rgba(31,31,61,0.7)', borderRadius: Radii.xxl, padding: 24, borderWidth: 1, borderColor: Colors.borderSoft },
  formError:     { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: Colors.danger + '18', borderRadius: 10, padding: 12, marginBottom: 12 },
  formErrorText: { color: Colors.danger, fontSize: 13, flex: 1 },
  label:         { color: Colors.textSub, fontSize: 13, marginBottom: 6, marginTop: 16 },
  inputWrap:     { flexDirection: 'row', alignItems: 'center', backgroundColor: 'rgba(11,11,31,0.6)', borderRadius: Radii.md, borderWidth: 1, borderColor: Colors.border, paddingHorizontal: 14, paddingVertical: 12, gap: 10 },
  inputError:    { borderColor: Colors.danger },
  input:         { flex: 1, color: Colors.text, fontSize: 15 },
  errorText:     { color: Colors.danger, fontSize: 12, marginTop: 4, marginLeft: 2 },
  strengthWrap:  { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 8 },
  strengthBar:   { flex: 1, flexDirection: 'row', gap: 4 },
  strengthSeg:   { flex: 1, height: 4, borderRadius: 2 },
  strengthLabel: { fontSize: 12, fontWeight: '600', minWidth: 84, textAlign: 'right' },
  strengthHint:  { color: Colors.textMuted, fontSize: 11, marginTop: 6, marginLeft: 2 },
  btn:           { borderRadius: Radii.lg, overflow: 'hidden', marginTop: 24, shadowColor: '#A78BFA', shadowOpacity: 0.5, shadowRadius: 18, shadowOffset: { width: 0, height: 0 }, elevation: 10 },
  btnInner:      { paddingVertical: 15, alignItems: 'center' },
  btnText:       { color: '#fff', fontWeight: '700', fontSize: 16 },
  switchRow:     { flexDirection: 'row', justifyContent: 'center', marginTop: 20 },
  switchText:    { color: Colors.textSub, fontSize: 14 },
});
