import axios, { AxiosInstance, InternalAxiosRequestConfig } from 'axios';
import Constants from 'expo-constants';
import { getAccessToken, getRefreshToken, setTokens, clearTokens } from './tokenStore';

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

export const INGESTION_URL =
  extra.ingestionUrl ??
  process.env.EXPO_PUBLIC_INGESTION_URL ??
  `http://${devHost}:8003`;

export const authClient      = axios.create({ baseURL: AUTH_URL,      timeout: 10000 });
export const analyticsClient = axios.create({ baseURL: ANALYTICS_URL, timeout: 10000 });
export const ingestionClient = axios.create({ baseURL: INGESTION_URL, timeout: 30000 });

// ── Token attach ──────────────────────────────────────────────────────────────

const attachToken = async (config: InternalAxiosRequestConfig) => {
  const token = await getAccessToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
};

analyticsClient.interceptors.request.use(attachToken);
authClient.interceptors.request.use(attachToken);
ingestionClient.interceptors.request.use(attachToken);

// ── Token refresh interceptor ─────────────────────────────────────────────────
// When any protected client gets a 401, silently refresh the access token once
// and replay the failed request. Concurrent 401s are queued so only one refresh
// call is made; if refresh itself fails, all queued requests are rejected and
// the stored tokens are cleared (user must log in again).

let isRefreshing = false;
type QueueEntry = { resolve: (token: string) => void; reject: (err: unknown) => void };
const failedQueue: QueueEntry[] = [];

function processQueue(error: unknown, token: string | null) {
  for (const entry of failedQueue) {
    if (error || !token) entry.reject(error);
    else entry.resolve(token);
  }
  failedQueue.length = 0;
}

async function attemptTokenRefresh(): Promise<string> {
  const refreshToken = await getRefreshToken();
  if (!refreshToken) throw new Error('No refresh token');

  const { data } = await axios.post(`${AUTH_URL}/auth/refresh`, { refresh_token: refreshToken });
  const newAccess: string = data.access_token;
  const newRefresh: string | undefined = data.refresh_token;

  await setTokens(newAccess, newRefresh);

  return newAccess;
}

function attachRefreshInterceptor(client: AxiosInstance) {
  client.interceptors.response.use(
    (response) => response,
    async (error) => {
      const originalRequest = error.config;
      if (error.response?.status !== 401 || originalRequest._retry) {
        return Promise.reject(error);
      }
      originalRequest._retry = true;

      if (isRefreshing) {
        return new Promise<string>((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then((token) => {
          originalRequest.headers.Authorization = `Bearer ${token}`;
          return client(originalRequest);
        });
      }

      isRefreshing = true;
      try {
        const newToken = await attemptTokenRefresh();
        processQueue(null, newToken);
        originalRequest.headers.Authorization = `Bearer ${newToken}`;
        return client(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        await clearTokens();
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    },
  );
}

attachRefreshInterceptor(analyticsClient);
attachRefreshInterceptor(authClient);
attachRefreshInterceptor(ingestionClient);
