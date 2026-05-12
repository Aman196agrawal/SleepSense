import axios from 'axios';
import Constants from 'expo-constants';
import AsyncStorage from '@react-native-async-storage/async-storage';

// Automatically detect the Expo dev-server host so it works on
// physical devices (Expo Go) without manual IP configuration.
const host = Constants.expoConfig?.hostUri?.split(':')[0] ?? 'localhost';

export const AUTH_URL    = `http://${host}:8001`;
export const ANALYTICS_URL = `http://${host}:8002`;

export const authClient = axios.create({ baseURL: AUTH_URL, timeout: 10000 });
export const analyticsClient = axios.create({ baseURL: ANALYTICS_URL, timeout: 10000 });

const attachToken = async (config: any) => {
  const token = await AsyncStorage.getItem('access_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
};

analyticsClient.interceptors.request.use(attachToken);
authClient.interceptors.request.use(attachToken);
