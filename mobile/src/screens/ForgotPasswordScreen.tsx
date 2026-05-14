import React, { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, StyleSheet, KeyboardAvoidingView, Platform, ScrollView } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { Colors } from '../theme/colors';
import { useAuthStore } from '../store/authStore';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { AuthStackParams } from '../navigation/AuthNavigator';

type Props = { navigation: NativeStackNavigationProp<AuthStackParams, 'ForgotPassword'> };

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function ForgotPasswordScreen({ navigation }: Props) {
  const [email, setEmail]     = useState('');
  const [loading, setLoading] = useState(false);
  const [sent, setSent]       = useState(false);
  const [error, setError]     = useState('');
  const { forgotPassword }    = useAuthStore();

  const handleSubmit = async () => {
    if (!email.trim() || !EMAIL_RE.test(email)) {
      setError('Enter a valid email address');
      return;
    }
    setLoading(true);
    setError('');
    try {
      await forgotPassword(email.trim().toLowerCase());
      setSent(true);
    } catch {
      setError('Something went wrong. Please try again.');
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

          <View style={styles.iconWrap}>
            <Ionicons name="lock-open-outline" size={48} color={Colors.primary} />
          </View>
          <Text style={styles.heading}>Forgot Password?</Text>
          <Text style={styles.sub}>
            Enter the email associated with your account and we'll send a reset link.
          </Text>

          {sent ? (
            <View style={styles.successCard}>
              <Ionicons name="checkmark-circle" size={40} color={Colors.excellent} />
              <Text style={styles.successTitle}>Check your email</Text>
              <Text style={styles.successBody}>
                If <Text style={{ color: Colors.primary }}>{email}</Text> is registered, a reset link has been sent.
                {'\n\n'}In dev mode, check the auth-service console for the link.
              </Text>
              <TouchableOpacity style={styles.backToLogin} onPress={() => navigation.navigate('ResetPassword')}>
                <Text style={styles.backToLoginText}>I have a reset token →</Text>
              </TouchableOpacity>
              <TouchableOpacity onPress={() => navigation.navigate('Login')} style={{ marginTop: 16 }}>
                <Text style={styles.switchText}>Back to Sign In</Text>
              </TouchableOpacity>
            </View>
          ) : (
            <View style={styles.card}>
              {error ? (
                <View style={styles.errBox}>
                  <Ionicons name="alert-circle-outline" size={16} color={Colors.danger} />
                  <Text style={styles.errText}>{error}</Text>
                </View>
              ) : null}

              <Text style={styles.label}>Email address</Text>
              <View style={[styles.inputWrap, error && styles.inputError]}>
                <Ionicons name="mail-outline" size={18} color={error ? Colors.danger : Colors.textMuted} />
                <TextInput
                  style={styles.input}
                  placeholder="you@example.com"
                  placeholderTextColor={Colors.textMuted}
                  value={email}
                  onChangeText={t => { setEmail(t); setError(''); }}
                  autoCapitalize="none"
                  keyboardType="email-address"
                />
              </View>

              <TouchableOpacity style={styles.btn} onPress={handleSubmit} disabled={loading}>
                <LinearGradient colors={[Colors.primary, Colors.primaryDark]} style={styles.btnInner}>
                  <Text style={styles.btnText}>{loading ? 'Sending…' : 'Send Reset Link'}</Text>
                </LinearGradient>
              </TouchableOpacity>

              <TouchableOpacity onPress={() => navigation.navigate('Login')} style={styles.switchRow}>
                <Text style={styles.switchText}>Remembered it? </Text>
                <Text style={[styles.switchText, { color: Colors.primary }]}>Sign in</Text>
              </TouchableOpacity>
            </View>
          )}
        </ScrollView>
      </KeyboardAvoidingView>
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  container:      { flexGrow: 1, paddingHorizontal: 24, paddingTop: 60, paddingBottom: 40 },
  back:           { marginBottom: 24 },
  iconWrap:       { alignItems: 'center', marginBottom: 16 },
  heading:        { fontSize: 26, fontWeight: '800', color: Colors.text, textAlign: 'center' },
  sub:            { color: Colors.textSub, textAlign: 'center', marginTop: 8, marginBottom: 28, lineHeight: 20 },
  card:           { backgroundColor: Colors.surface, borderRadius: 20, padding: 24 },
  errBox:         { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: Colors.danger + '18', borderRadius: 10, padding: 12, marginBottom: 12 },
  errText:        { color: Colors.danger, fontSize: 13, flex: 1 },
  label:          { color: Colors.textSub, fontSize: 13, marginBottom: 6, marginTop: 4 },
  inputWrap:      { flexDirection: 'row', alignItems: 'center', backgroundColor: Colors.bg, borderRadius: 12, borderWidth: 1, borderColor: Colors.border, paddingHorizontal: 14, paddingVertical: 12, gap: 10 },
  inputError:     { borderColor: Colors.danger },
  input:          { flex: 1, color: Colors.text, fontSize: 15 },
  btn:            { borderRadius: 12, overflow: 'hidden', marginTop: 24 },
  btnInner:       { paddingVertical: 15, alignItems: 'center' },
  btnText:        { color: '#fff', fontWeight: '700', fontSize: 16 },
  switchRow:      { flexDirection: 'row', justifyContent: 'center', marginTop: 20 },
  switchText:     { color: Colors.textSub, fontSize: 14 },
  successCard:    { backgroundColor: Colors.surface, borderRadius: 20, padding: 28, alignItems: 'center' },
  successTitle:   { color: Colors.text, fontSize: 20, fontWeight: '700', marginTop: 16, marginBottom: 12 },
  successBody:    { color: Colors.textSub, textAlign: 'center', lineHeight: 22 },
  backToLogin:    { marginTop: 24, paddingVertical: 12, paddingHorizontal: 20, borderRadius: 12, borderWidth: 1, borderColor: Colors.primary },
  backToLoginText:{ color: Colors.primary, fontWeight: '600' },
});
