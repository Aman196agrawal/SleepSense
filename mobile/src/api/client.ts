import axios from 'axios';
import Constants from 'expo-constants';
import AsyncStorage from '@react-native-async-storage/async-storage';

// Resolve the backend base URL in this priority order:
//   1. `extra.authUrl`/`extra.analyticsUrl` in app.json (set per EAS build profile)
//   2. EXPO_PUBLIC_AUTH_URL / EXPO_PUBLIC_ANALYTICS_URL env vars at build time
//   3. The Expo dev server's host IP (so Expo Go on a physical device on the
//      same LAN can reach your laptop's services without manual config)
//   4. localhost (web / simulator)
const extra = (Constants.expoConfig?.extra ?? {}) as Record<string, string | undefined>;
const devHost = Constants.expoConfig?.hostUri?.split(':')[0] ?? 'localhost';

export const AUTH_URL =
  extra.authUrl ??
  process.env.EXPO_PUBLIC_AUTH_URL ??
  `http://${devHost}:8001`;

export const ANALYTICS_URL =
  extra.analyticsUrl ??
  process.env.EXPO_PUBLIC_ANALYTICS_URL ??
  `http://${devHost}:8002`;

export const authClient = axios.create({ baseURL: AUTH_URL, timeout: 10000 });
export const analyticsClient = axios.create({ baseURL: ANALYTICS_URL, timeout: 10000 });

const attachToken = async (config: any) => {
  const token = await AsyncStorage.getItem('access_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
};

analyticsClient.interceptors.request.use(attachToken);
authClient.interceptors.request.use(attachToken);
