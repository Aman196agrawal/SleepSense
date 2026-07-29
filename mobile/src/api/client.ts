import axios, { AxiosInstance, InternalAxiosRequestConfig } from 'axios';
import { getAccessToken, getRefreshToken, setTokens, clearTokens } from './tokenStore';
import { getAuthUrl, getAnalyticsUrl, getIngestionUrl } from './config';

// These instances deliberately carry NO baseURL. A baseURL passed to
// axios.create() is captured at import time, which is exactly what made the
// backend URL un-changeable without a rebuild. Instead the request interceptor
// below stamps `config.baseURL` from the live config on every request, so
// saving a new URL in Settings takes effect on the next call — no app reload,
// no Metro restart, no Gradle build. Every module that already imported these
// instances keeps working, because the instance identity never changes.

export const authClient      = axios.create({ timeout: 10000 });
export const analyticsClient = axios.create({ timeout: 10000 });
export const ingestionClient = axios.create({ timeout: 30000 });

// ── Base URL + token attach ───────────────────────────────────────────────────

function attachBaseUrlAndToken(client: AxiosInstance, resolveBaseUrl: () => string) {
  client.interceptors.request.use(async (config: InternalAxiosRequestConfig) => {
    config.baseURL = resolveBaseUrl();
    const token = await getAccessToken();
    if (token) config.headers.Authorization = `Bearer ${token}`;
    return config;
  });
}

attachBaseUrlAndToken(analyticsClient, getAnalyticsUrl);
attachBaseUrlAndToken(authClient,      getAuthUrl);
attachBaseUrlAndToken(ingestionClient, getIngestionUrl);

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

  // Bare axios (not authClient) so this never recurses through the 401
  // interceptor; resolve the URL at call time for the same reason as above.
  const { data } = await axios.post(`${getAuthUrl()}/auth/refresh`, { refresh_token: refreshToken });
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
