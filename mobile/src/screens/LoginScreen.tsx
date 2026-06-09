import React, { useState, useEffect, useRef } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  KeyboardAvoidingView, Platform, ScrollView, Alert, ActivityIndicator, Vibration,
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import * as Google from 'expo-auth-session/providers/google';
import * as WebBrowser from 'expo-web-browser';
import { Colors, Gradients, Radii } from '../theme';
import AuroraBackground from '../components/AuroraBackground';
import { useAuthStore } from '../store/authStore';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { AuthStackParams } from '../navigation/AuthNavigator';

WebBrowser.maybeCompleteAuthSession();

type Props = { navigation: NativeStackNavigationProp<AuthStackParams, 'Login'> };

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function LoginScreen({ navigation }: Props) {
  const [email, setEmail]             = useState('');
  const [password, setPassword]       = useState('');
  const [loading, setLoading]         = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [showPw, setShowPw]           = useState(false);
  const [errors, setErrors]           = useState<{ email?: string; password?: string; form?: string }>({});
  const { login, socialLoginGoogle }  = useAuthStore();
  const passwordRef = useRef<TextInput>(null);

  // Fallback to 'not-configured' so the hook doesn't throw an invariant when
  // Google OAuth env vars aren't set in dev. The button guard in handleGoogleSignIn
  // shows an alert before promptAsync() is ever called in that case.
  const [, response, promptAsync] = Google.useAuthRequest({
    androidClientId: process.env.EXPO_PUBLIC_GOOGLE_ANDROID_CLIENT_ID ?? 'not-configured',
    iosClientId:     process.env.EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID     ?? 'not-configured',
    webClientId:     process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID,
  });

  useEffect(() => {
    if (!response) return;
    if (response.type === 'success') {
      const idToken = response.authentication?.idToken;
      if (!idToken) {
        setErrors({ form: 'Google did not return an ID token. Ensure a webClientId is configured.' });
        return;
      }
      setGoogleLoading(true);
      socialLoginGoogle(idToken)
        .catch((e: any) => {
          const detail = e?.response?.data?.detail ?? 'Google sign-in failed. Please try again.';
          setErrors({ form: detail });
        })
        .finally(() => setGoogleLoading(false));
    } else if (response.type === 'error') {
      setErrors({ form: response.error?.message ?? 'Google sign-in was cancelled or failed.' });
    }
  }, [response]);

  const clearErr = (key: keyof typeof errors) =>
    setErrors(prev => { const n = { ...prev }; delete n[key]; return n; });

  const validate = () => {
    const e: typeof errors = {};
    if (!email.trim())              e.email    = 'Email is required';
    else if (!EMAIL_RE.test(email)) e.email    = 'Enter a valid email address';
    if (!password)                  e.password = 'Password is required';
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleLogin = async () => {
    if (!validate()) return;
    Vibration.vibrate(15);
    setLoading(true);
    setErrors({});
    try {
      await login(email.trim().toLowerCase(), password);
    } catch (e: any) {
      const detail = e?.response?.data?.detail ?? '';
      if (e?.response?.status === 429) {
        setErrors({ form: 'Too many login attempts. Please try again in 15 minutes.' });
      } else {
        setErrors({ form: detail || 'Invalid email or password' });
      }
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleSignIn = async () => {
    const hasConfig =
      process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID ||
      process.env.EXPO_PUBLIC_GOOGLE_ANDROID_CLIENT_ID ||
      process.env.EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID;

    if (!hasConfig) {
      Alert.alert(
        'Google Sign-In Not Configured',
        'Set EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID (and platform IDs) in your .env file to enable Google login.',
      );
      return;
    }
    setErrors({});
    await promptAsync();
  };

  return (
    <AuroraBackground style={{ flex: 1 }}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
          <View style={styles.logoWrap}>
            <LinearGradient
              colors={Gradients.cta as any}
              start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
              style={styles.logoBadge}
            >
              <Ionicons name="moon" size={32} color="#fff" />
            </LinearGradient>
            <Text style={styles.appName}>SleepSense</Text>
            <Text style={styles.tagline}>Sleep better, live better</Text>
          </View>

          <View style={styles.card}>
            <Text style={styles.heading}>Welcome back</Text>

            {errors.form && (
              <View style={styles.formError}>
                <Ionicons name="alert-circle-outline" size={16} color={Colors.danger} />
                <Text style={styles.formErrorText}>{errors.form}</Text>
              </View>
            )}

            <Text style={styles.label}>Email</Text>
            <View style={[styles.inputWrap, errors.email && styles.inputError]}>
              <Ionicons name="mail-outline" size={18} color={errors.email ? Colors.danger : Colors.textMuted} />
              <TextInput
                style={styles.input}
                placeholder="you@example.com"
                placeholderTextColor={Colors.textMuted}
                value={email}
                onChangeText={t => { setEmail(t); clearErr('email'); }}
                autoCapitalize="none"
                keyboardType="email-address"
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
                ref={passwordRef}
                style={styles.input}
                placeholder="••••••••"
                placeholderTextColor={Colors.textMuted}
                value={password}
                onChangeText={t => { setPassword(t); clearErr('password'); }}
                secureTextEntry={!showPw}
                returnKeyType="done"
                onSubmitEditing={handleLogin}
              />
              <TouchableOpacity onPress={() => setShowPw(!showPw)}>
                <Ionicons name={showPw ? 'eye-off-outline' : 'eye-outline'} size={18} color={Colors.textMuted} />
              </TouchableOpacity>
            </View>
            {errors.password && <Text style={styles.errorText}>{errors.password}</Text>}

            <TouchableOpacity style={styles.forgotRow} onPress={() => navigation.navigate('ForgotPassword')}>
              <Text style={styles.forgotText}>Forgot password?</Text>
            </TouchableOpacity>

            <TouchableOpacity style={styles.btn} onPress={handleLogin} disabled={loading || googleLoading}>
              <LinearGradient colors={Gradients.cta as any} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} style={styles.btnInner}>
                <Text style={styles.btnText}>{loading ? 'Signing in…' : 'Sign In'}</Text>
              </LinearGradient>
            </TouchableOpacity>

            <View style={styles.dividerRow}>
              <View style={styles.dividerLine} />
              <Text style={styles.dividerText}>or</Text>
              <View style={styles.dividerLine} />
            </View>

            <TouchableOpacity
              style={[styles.googleBtn, googleLoading && { opacity: 0.6 }]}
              onPress={handleGoogleSignIn}
              disabled={loading || googleLoading}
            >
              {googleLoading ? (
                <ActivityIndicator size="small" color={Colors.primary} />
              ) : (
                <View style={styles.googleIconWrap}>
                  <Text style={styles.googleG}>G</Text>
                </View>
              )}
              <Text style={styles.googleText}>
                {googleLoading ? 'Signing in…' : 'Continue with Google'}
              </Text>
            </TouchableOpacity>

            <TouchableOpacity onPress={() => navigation.navigate('Register')} style={styles.switchRow}>
              <Text style={styles.switchText}>Don't have an account? </Text>
              <Text style={[styles.switchText, { color: Colors.primary }]}>Create one</Text>
            </TouchableOpacity>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </AuroraBackground>
  );
}

const styles = StyleSheet.create({
  container:     { flexGrow: 1, paddingHorizontal: 24, paddingTop: 60, paddingBottom: 40 },
  logoWrap:      { alignItems: 'center', marginBottom: 32 },
  logoBadge:     { width: 64, height: 64, borderRadius: 20, alignItems: 'center', justifyContent: 'center', shadowColor: '#A78BFA', shadowOpacity: 0.55, shadowRadius: 20, shadowOffset: { width: 0, height: 0 }, elevation: 12 },
  appName:       { fontSize: 30, fontWeight: '800', color: Colors.text, marginTop: 14, letterSpacing: -0.8 },
  tagline:       { color: Colors.textSub, marginTop: 4, fontSize: 13, fontWeight: '500' },
  card:          { backgroundColor: 'rgba(31,31,61,0.7)', borderRadius: Radii.xxl, padding: 24, borderWidth: 1, borderColor: Colors.borderSoft },
  heading:       { fontSize: 22, fontWeight: '800', color: Colors.text, marginBottom: 20, letterSpacing: -0.4 },
  formError:     { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: Colors.danger + '20', borderRadius: 10, padding: 12, marginBottom: 12, borderWidth: 1, borderColor: Colors.danger + '44' },
  formErrorText: { color: Colors.danger, fontSize: 13, flex: 1 },
  label:         { color: Colors.textSub, fontSize: 13, marginBottom: 6, marginTop: 16, fontWeight: '600' },
  inputWrap:     { flexDirection: 'row', alignItems: 'center', backgroundColor: 'rgba(11,11,31,0.6)', borderRadius: Radii.md, borderWidth: 1, borderColor: Colors.border, paddingHorizontal: 14, paddingVertical: 12, gap: 10 },
  inputError:    { borderColor: Colors.danger },
  input:         { flex: 1, color: Colors.text, fontSize: 15 },
  errorText:     { color: Colors.danger, fontSize: 12, marginTop: 4, marginLeft: 2 },
  forgotRow:     { alignSelf: 'flex-end', marginTop: 10 },
  forgotText:    { color: Colors.primary, fontSize: 13, fontWeight: '600' },
  btn:           { borderRadius: Radii.lg, overflow: 'hidden', marginTop: 24, shadowColor: '#A78BFA', shadowOpacity: 0.5, shadowRadius: 18, shadowOffset: { width: 0, height: 0 }, elevation: 10 },
  btnInner:      { paddingVertical: 15, alignItems: 'center' },
  btnText:       { color: '#fff', fontWeight: '800', fontSize: 16, letterSpacing: 0.2 },
  dividerRow:    { flexDirection: 'row', alignItems: 'center', gap: 12, marginVertical: 20 },
  dividerLine:   { flex: 1, height: 1, backgroundColor: Colors.border },
  dividerText:   { color: Colors.textMuted, fontSize: 12, fontWeight: '600', letterSpacing: 1 },
  googleBtn:     { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 12, borderRadius: Radii.md, borderWidth: 1, borderColor: Colors.border, paddingVertical: 13, backgroundColor: 'rgba(11,11,31,0.5)' },
  googleIconWrap:{ width: 22, height: 22, borderRadius: 11, backgroundColor: '#fff', alignItems: 'center', justifyContent: 'center' },
  googleG:       { color: '#4285F4', fontWeight: '800', fontSize: 13 },
  googleText:    { color: Colors.text, fontWeight: '600', fontSize: 14 },
  switchRow:     { flexDirection: 'row', justifyContent: 'center', marginTop: 20 },
  switchText:    { color: Colors.textSub, fontSize: 14 },
});
