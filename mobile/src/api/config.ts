import AsyncStorage from '@react-native-async-storage/async-storage';
import Constants from 'expo-constants';

// Runtime-configurable backend URLs.
//
// Resolution order, highest priority first:
//   1. AsyncStorage override  — set from Profile → Backend URLs, no rebuild needed
//   2. app.json expo.extra    — baked in at build time
//   3. EXPO_PUBLIC_* env var  — baked in at bundle time
//   4. hostUri-derived default — the Metro host, for `expo start` on a LAN
//
// (2) shadows (3) whenever app.json sets `extra`, which it currently does for
// all three URLs. That is intentional — layer (1) is what makes the URL
// changeable at runtime, which is the whole point of this module.

export type ApiUrlKey = 'authUrl' | 'analyticsUrl' | 'ingestionUrl';
export type ApiUrls = Record<ApiUrlKey, string>;

export const API_URL_KEYS: ApiUrlKey[] = ['authUrl', 'analyticsUrl', 'ingestionUrl'];

export const STORAGE_KEYS: Record<ApiUrlKey, string> = {
  authUrl:      'api.authUrl',
  analyticsUrl: 'api.analyticsUrl',
  ingestionUrl: 'api.ingestionUrl',
};

export const API_URL_LABELS: Record<ApiUrlKey, string> = {
  authUrl:      'Auth service',
  analyticsUrl: 'Analytics service',
  ingestionUrl: 'Ingestion service',
};

const extra   = (Constants.expoConfig?.extra ?? {}) as Record<string, string | undefined>;
const devHost = Constants.expoConfig?.hostUri?.split(':')[0] ?? 'localhost';

export const API_DEFAULTS: ApiUrls = {
  authUrl:      extra.authUrl      ?? process.env.EXPO_PUBLIC_AUTH_URL      ?? `http://${devHost}:8001`,
  analyticsUrl: extra.analyticsUrl ?? process.env.EXPO_PUBLIC_ANALYTICS_URL ?? `http://${devHost}:8002`,
  ingestionUrl: extra.ingestionUrl ?? process.env.EXPO_PUBLIC_INGESTION_URL ?? `http://${devHost}:8003`,
};

// ── Validation ────────────────────────────────────────────────────────────────
// Hand-rolled rather than `new URL()`: React Native's URL polyfill is not
// spec-compliant and does not reliably throw on malformed input, so relying on
// it to reject bad values would let garbage through into the request baseURL.

export type UrlValidation =
  | { ok: true;  value: string }
  | { ok: false; error: string };

export function normalizeBaseUrl(raw: string): UrlValidation {
  const input = raw.trim();
  if (!input) return { ok: false, error: 'Enter a URL.' };

  const parts = /^([a-zA-Z][a-zA-Z0-9+.-]*):\/\/(.*)$/.exec(input);
  if (!parts) return { ok: false, error: 'Missing scheme — start with http:// or https://' };

  const scheme = parts[1].toLowerCase();
  if (scheme !== 'http' && scheme !== 'https') {
    return { ok: false, error: `Unsupported scheme "${scheme}" — use http or https.` };
  }

  const rest = parts[2];
  if (/[?#]/.test(rest)) {
    return { ok: false, error: 'A base URL cannot contain a query string or fragment.' };
  }

  const slash     = rest.indexOf('/');
  const authority = slash === -1 ? rest : rest.slice(0, slash);
  const path      = slash === -1 ? ''   : rest.slice(slash);

  // Drop any userinfo ("user:pass@host") before splitting host from port.
  const hostAndPort = authority.slice(authority.lastIndexOf('@') + 1);
  if (!hostAndPort) return { ok: false, error: 'Missing host.' };

  // Bracketed IPv6 literals keep their brackets; everything else splits on ':'.
  let host: string;
  if (hostAndPort.startsWith('[')) {
    const close = hostAndPort.indexOf(']');
    if (close === -1) return { ok: false, error: 'Unclosed IPv6 bracket in host.' };
    host = hostAndPort.slice(0, close + 1);
    if (host === '[]') return { ok: false, error: 'Missing host.' };
  } else {
    host = hostAndPort.split(':')[0];
    if (!host) return { ok: false, error: 'Missing host.' };
    if (/[^a-zA-Z0-9.\-_]/.test(host)) {
      return { ok: false, error: `Invalid character in host "${host}".` };
    }
  }

  const portPart = hostAndPort.slice(host.length);
  if (portPart) {
    if (!/^:\d{1,5}$/.test(portPart)) {
      return { ok: false, error: 'Port must be a number, e.g. :8001' };
    }
    const port = Number(portPart.slice(1));
    if (port < 1 || port > 65535) {
      return { ok: false, error: 'Port must be between 1 and 65535.' };
    }
  }

  // Strip trailing slashes so callers can safely concatenate "/auth/login".
  const cleanPath = path.replace(/\/+$/, '');

  return { ok: true, value: `${scheme}://${hostAndPort}${cleanPath}` };
}

// ── In-memory cache ───────────────────────────────────────────────────────────
// Kept synchronous on purpose: the axios request interceptor reads it on every
// request and must not await AsyncStorage in the hot path. `loadApiConfig()`
// hydrates it once at startup; `saveApiOverrides()` updates it in place, so a
// change takes effect on the very next request with no reload.

let cache: ApiUrls = { ...API_DEFAULTS };
let loaded = false;
let inFlight: Promise<ApiUrls> | null = null;

export function getApiUrls(): ApiUrls { return cache; }
export function getAuthUrl(): string      { return cache.authUrl; }
export function getAnalyticsUrl(): string { return cache.analyticsUrl; }
export function getIngestionUrl(): string { return cache.ingestionUrl; }

export async function loadApiConfig(): Promise<ApiUrls> {
  if (loaded)   return cache;
  if (inFlight) return inFlight;

  inFlight = (async () => {
    try {
      const pairs = await AsyncStorage.multiGet(API_URL_KEYS.map(k => STORAGE_KEYS[k]));
      const stored: Record<string, string | null> = {};
      for (const [k, v] of pairs) stored[k] = v;

      const next: ApiUrls = { ...API_DEFAULTS };
      for (const key of API_URL_KEYS) {
        const raw = stored[STORAGE_KEYS[key]];
        if (!raw) continue;
        const parsed = normalizeBaseUrl(raw);
        // Ignore a corrupt stored value rather than bricking the app with it.
        if (parsed.ok) next[key] = parsed.value;
        else console.warn(`[apiConfig] discarding invalid stored ${key}: ${parsed.error}`);
      }
      cache = next;
    } catch (err) {
      console.warn('[apiConfig] could not read overrides, using defaults', err);
    } finally {
      loaded   = true;
      inFlight = null;
    }
    return cache;
  })();

  return inFlight;
}

/** Validate and persist overrides. Throws on the first invalid value. */
export async function saveApiOverrides(next: Partial<ApiUrls>): Promise<ApiUrls> {
  const entries: [string, string][] = [];
  const applied: Partial<ApiUrls>   = {};

  for (const key of API_URL_KEYS) {
    const raw = next[key];
    if (raw === undefined) continue;
    const parsed = normalizeBaseUrl(raw);
    if (!parsed.ok) throw new Error(`${API_URL_LABELS[key]}: ${parsed.error}`);
    entries.push([STORAGE_KEYS[key], parsed.value]);
    applied[key] = parsed.value;
  }

  if (entries.length) await AsyncStorage.multiSet(entries);
  cache  = { ...cache, ...applied };
  loaded = true;
  return cache;
}

/** Drop all overrides and fall back to the build-time defaults. */
export async function resetApiOverrides(): Promise<ApiUrls> {
  await AsyncStorage.multiRemove(API_URL_KEYS.map(k => STORAGE_KEYS[k]));
  cache  = { ...API_DEFAULTS };
  loaded = true;
  return cache;
}

/** True when the effective URL differs from the build-time default. */
export function isOverridden(key: ApiUrlKey): boolean {
  return cache[key] !== API_DEFAULTS[key];
}
