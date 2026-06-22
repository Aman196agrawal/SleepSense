/**
 * Secure token storage.
 *
 * Access + refresh JWTs are kept in the device keychain/keystore via
 * expo-secure-store instead of AsyncStorage (which is an unencrypted file/SQLite
 * on Android, readable on rooted devices and in backups).
 *
 * - Native (iOS/Android): expo-secure-store (Keychain / Keystore).
 * - Web (react-native-web): SecureStore is unavailable, so fall back to
 *   AsyncStorage — acceptable for the dev web preview only.
 *
 * A one-time migration moves any tokens left in AsyncStorage by older builds into
 * SecureStore on first read, so existing sessions survive the upgrade.
 */
import { Platform } from 'react-native';
import * as SecureStore from 'expo-secure-store';
import AsyncStorage from '@react-native-async-storage/async-storage';

const ACCESS_KEY = 'access_token';
const REFRESH_KEY = 'refresh_token';

const useSecure = Platform.OS !== 'web';

async function readKey(key: string): Promise<string | null> {
  if (!useSecure) return AsyncStorage.getItem(key);
  try {
    const secure = await SecureStore.getItemAsync(key);
    if (secure !== null) return secure;
    // Migrate a token written by an older (AsyncStorage) build, then drop it.
    const legacy = await AsyncStorage.getItem(key);
    if (legacy !== null) {
      await SecureStore.setItemAsync(key, legacy);
      await AsyncStorage.removeItem(key);
      return legacy;
    }
    return null;
  } catch {
    return null;
  }
}

async function writeKey(key: string, value: string): Promise<void> {
  if (!useSecure) {
    await AsyncStorage.setItem(key, value);
    return;
  }
  await SecureStore.setItemAsync(key, value);
}

export const getAccessToken = () => readKey(ACCESS_KEY);
export const getRefreshToken = () => readKey(REFRESH_KEY);

export async function setTokens(access: string, refresh?: string): Promise<void> {
  await writeKey(ACCESS_KEY, access);
  if (refresh) await writeKey(REFRESH_KEY, refresh);
}

export async function clearTokens(): Promise<void> {
  if (useSecure) {
    await SecureStore.deleteItemAsync(ACCESS_KEY).catch(() => {});
    await SecureStore.deleteItemAsync(REFRESH_KEY).catch(() => {});
  }
  // Always also clear any legacy AsyncStorage copies.
  await AsyncStorage.multiRemove([ACCESS_KEY, REFRESH_KEY]).catch(() => {});
}
