import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, TextInput, StyleSheet, TouchableOpacity, ScrollView,
  Alert, ActivityIndicator, KeyboardAvoidingView, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import axios from 'axios';
import { useNavigation } from '@react-navigation/native';
import { Colors, Gradients, Radii } from '../theme';
import AuroraBackground from '../components/AuroraBackground';
import { sleepSenseWS } from '../api/ws';
import {
  API_DEFAULTS, API_URL_KEYS, API_URL_LABELS,
  getApiUrls, isOverridden, normalizeBaseUrl,
  resetApiOverrides, saveApiOverrides,
  type ApiUrlKey, type ApiUrls,
} from '../api/config';

type TestResult = { ok: boolean; text: string };

export default function ApiSettingsScreen() {
  const navigation = useNavigation();

  const [draft, setDraft]       = useState<ApiUrls>(() => ({ ...getApiUrls() }));
  const [errors, setErrors]     = useState<Partial<Record<ApiUrlKey, string>>>({});
  const [saving, setSaving]     = useState(false);
  const [testing, setTesting]   = useState(false);
  const [result, setResult]     = useState<TestResult | null>(null);

  // Re-sync if the cache changed while this screen was mounted but unfocused.
  useEffect(() => { setDraft({ ...getApiUrls() }); }, []);

  const edit = useCallback((key: ApiUrlKey, value: string) => {
    setDraft(d => ({ ...d, [key]: value }));
    setErrors(e => ({ ...e, [key]: undefined }));
    setResult(null);
  }, []);

  const validateAll = (): ApiUrls | null => {
    const next   = {} as ApiUrls;
    const found: Partial<Record<ApiUrlKey, string>> = {};
    for (const key of API_URL_KEYS) {
      const parsed = normalizeBaseUrl(draft[key]);
      if (parsed.ok) next[key] = parsed.value;
      else found[key] = parsed.error;
    }
    setErrors(found);
    return Object.keys(found).length ? null : next;
  };

  const handleSave = async () => {
    const valid = validateAll();
    if (!valid) return;

    setSaving(true);
    try {
      const applied = await saveApiOverrides(valid);
      setDraft({ ...applied });
      setResult(null);
      // Force the socket to redial the (possibly new) analytics host. HTTP
      // needs no equivalent — the axios interceptor re-reads the URL per call.
      sleepSenseWS.disconnect();
      Alert.alert('Saved', 'Backend URLs updated. New requests use them immediately.');
    } catch (err) {
      Alert.alert('Could not save', err instanceof Error ? err.message : 'Unknown error.');
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    Alert.alert(
      'Reset to defaults',
      'Discard your saved URLs and go back to the ones baked into this build?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Reset',
          style: 'destructive',
          onPress: async () => {
            const defaults = await resetApiOverrides();
            setDraft({ ...defaults });
            setErrors({});
            setResult(null);
            sleepSenseWS.disconnect();
          },
        },
      ],
    );
  };

  // Tests whatever is currently typed in the Auth field, so you can check a URL
  // before committing it. Bare axios: authClient would rewrite the baseURL to
  // the saved value and defeat the point.
  const handleTest = async () => {
    const parsed = normalizeBaseUrl(draft.authUrl);
    if (!parsed.ok) {
      setErrors(e => ({ ...e, authUrl: parsed.error }));
      return;
    }

    setTesting(true);
    setResult(null);
    const startedAt = Date.now();
    try {
      const res = await axios.get(`${parsed.value}/health`, { timeout: 8000 });
      const ms  = Date.now() - startedAt;
      const status = typeof res.data?.status === 'string' ? ` · ${res.data.status}` : '';
      setResult({ ok: true, text: `HTTP ${res.status}${status} · ${ms} ms\n${parsed.value}/health` });
    } catch (err) {
      const ms = Date.now() - startedAt;
      let detail: string;
      if (axios.isAxiosError(err)) {
        if (err.response)              detail = `HTTP ${err.response.status} ${err.response.statusText ?? ''}`.trim();
        else if (err.code === 'ECONNABORTED') detail = 'Timed out after 8 s';
        else                           detail = err.message;
      } else {
        detail = err instanceof Error ? err.message : 'Unknown error';
      }
      setResult({ ok: false, text: `${detail} · ${ms} ms\n${parsed.value}/health` });
    } finally {
      setTesting(false);
    }
  };

  return (
    <AuroraBackground style={{ flex: 1 }}>
      <SafeAreaView style={{ flex: 1 }} edges={['top']}>
        <KeyboardAvoidingView
          style={{ flex: 1 }}
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        >
          <View style={styles.header}>
            <TouchableOpacity onPress={() => navigation.goBack()} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}>
              <Ionicons name="chevron-back" size={24} color={Colors.text} />
            </TouchableOpacity>
            <Text style={styles.headerTitle}>Backend URLs</Text>
            <View style={{ width: 24 }} />
          </View>

          <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
            <Text style={styles.blurb}>
              Point the app at a different server without rebuilding. Saved here, these
              override the URLs baked into the build and apply to the next request.
            </Text>

            {API_URL_KEYS.map(key => (
              <View key={key} style={styles.field}>
                <View style={styles.labelRow}>
                  <Text style={styles.label}>{API_URL_LABELS[key]}</Text>
                  {isOverridden(key) && <Text style={styles.badge}>OVERRIDDEN</Text>}
                </View>
                <View style={[styles.inputWrap, errors[key] ? styles.inputWrapError : null]}>
                  <TextInput
                    style={styles.input}
                    value={draft[key]}
                    onChangeText={t => edit(key, t)}
                    placeholder={API_DEFAULTS[key]}
                    placeholderTextColor={Colors.textMuted}
                    autoCapitalize="none"
                    autoCorrect={false}
                    keyboardType="url"
                    spellCheck={false}
                  />
                </View>
                {errors[key]
                  ? <Text style={styles.errorText}>{errors[key]}</Text>
                  : <Text style={styles.hint}>Default: {API_DEFAULTS[key]}</Text>}
              </View>
            ))}

            <TouchableOpacity style={styles.primaryBtn} onPress={handleSave} disabled={saving}>
              <LinearGradient
                colors={Gradients.cta as any}
                start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }}
                style={styles.primaryBtnInner}
              >
                {saving
                  ? <ActivityIndicator size="small" color="#fff" />
                  : <Text style={styles.primaryBtnText}>Save</Text>}
              </LinearGradient>
            </TouchableOpacity>

            <View style={styles.secondaryRow}>
              <TouchableOpacity style={styles.secondaryBtn} onPress={handleTest} disabled={testing}>
                {testing
                  ? <ActivityIndicator size="small" color={Colors.primary} />
                  : <>
                      <Ionicons name="pulse-outline" size={16} color={Colors.primary} />
                      <Text style={styles.secondaryBtnText}>Test connection</Text>
                    </>}
              </TouchableOpacity>

              <TouchableOpacity
                style={[styles.secondaryBtn, { borderColor: Colors.danger + '44' }]}
                onPress={handleReset}
              >
                <Ionicons name="refresh-outline" size={16} color={Colors.danger} />
                <Text style={[styles.secondaryBtnText, { color: Colors.danger }]}>Reset</Text>
              </TouchableOpacity>
            </View>

            {result && (
              <View style={[styles.result, { borderColor: (result.ok ? Colors.excellent : Colors.danger) + '55' }]}>
                <Ionicons
                  name={result.ok ? 'checkmark-circle' : 'close-circle'}
                  size={18}
                  color={result.ok ? Colors.excellent : Colors.danger}
                />
                <Text style={[styles.resultText, { color: result.ok ? Colors.excellent : Colors.danger }]}>
                  {result.text}
                </Text>
              </View>
            )}
          </ScrollView>
        </KeyboardAvoidingView>
      </SafeAreaView>
    </AuroraBackground>
  );
}

const styles = StyleSheet.create({
  header:          { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 20, paddingBottom: 12 },
  headerTitle:     { color: Colors.text, fontSize: 17, fontWeight: '800', letterSpacing: -0.2 },
  container:       { padding: 20, paddingBottom: 140 },
  blurb:           { color: Colors.textSub, fontSize: 13, lineHeight: 19, marginBottom: 24 },
  field:           { marginBottom: 18 },
  labelRow:        { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8, marginLeft: 2 },
  label:           { color: Colors.textMuted, fontSize: 11, fontWeight: '700', letterSpacing: 1.2, textTransform: 'uppercase' },
  badge:           { color: Colors.primary, fontSize: 9, fontWeight: '800', letterSpacing: 0.8, backgroundColor: Colors.primaryDim, paddingHorizontal: 6, paddingVertical: 2, borderRadius: Radii.xs, overflow: 'hidden' },
  inputWrap:       { backgroundColor: Colors.surfaceGlass, borderRadius: Radii.md, borderWidth: 1, borderColor: Colors.borderSoft, paddingHorizontal: 14, paddingVertical: Platform.OS === 'ios' ? 14 : 4 },
  inputWrapError:  { borderColor: Colors.danger + '88' },
  input:           { color: Colors.text, fontSize: 14 },
  hint:            { color: Colors.textMuted, fontSize: 11, marginTop: 5, marginLeft: 2 },
  errorText:       { color: Colors.danger, fontSize: 12, marginTop: 5, marginLeft: 2 },
  primaryBtn:      { borderRadius: Radii.lg, overflow: 'hidden', marginTop: 10 },
  primaryBtnInner: { paddingVertical: 15, alignItems: 'center' },
  primaryBtnText:  { color: '#fff', fontWeight: '800', fontSize: 16, letterSpacing: 0.2 },
  secondaryRow:    { flexDirection: 'row', gap: 10, marginTop: 12 },
  secondaryBtn:    { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 7, paddingVertical: 13, borderRadius: Radii.lg, borderWidth: 1, borderColor: Colors.borderSoft },
  secondaryBtnText:{ color: Colors.primary, fontWeight: '700', fontSize: 13 },
  result:          { flexDirection: 'row', alignItems: 'flex-start', gap: 10, marginTop: 18, padding: 14, borderRadius: Radii.md, borderWidth: 1, backgroundColor: Colors.surfaceGlass },
  resultText:      { flex: 1, fontSize: 12, lineHeight: 17, fontWeight: '600' },
});
