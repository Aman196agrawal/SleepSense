import { create } from 'zustand';
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as AuthAPI from '../api/auth.api';

interface User { id: string; email: string; display_name?: string; timezone: string; }

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name: string) => Promise<void>;
  socialLoginGoogle: (id_token: string) => Promise<void>;
  forgotPassword: (email: string) => Promise<void>;
  resetPassword: (token: string, new_password: string) => Promise<void>;
  logout: () => Promise<void>;
  hydrate: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  accessToken: null,
  refreshToken: null,
  isLoading: true,

  hydrate: async () => {
    const token = await AsyncStorage.getItem('access_token');
    if (token) {
      try {
        const res = await AuthAPI.getMe();
        set({ user: res.data, accessToken: token, isLoading: false });
      } catch {
        await AsyncStorage.multiRemove(['access_token', 'refresh_token']);
        set({ isLoading: false });
      }
    } else {
      set({ isLoading: false });
    }
  },

  login: async (email, password) => {
    const res = await AuthAPI.login(email, password);
    const { access_token, refresh_token } = res.data;
    await AsyncStorage.multiSet([['access_token', access_token], ['refresh_token', refresh_token]]);
    const me = await AuthAPI.getMe();
    set({ user: me.data, accessToken: access_token, refreshToken: refresh_token });
  },

  register: async (email, password, name) => {
    const res = await AuthAPI.register(email, password, name);
    const { access_token, refresh_token } = res.data;
    await AsyncStorage.multiSet([['access_token', access_token], ['refresh_token', refresh_token]]);
    const me = await AuthAPI.getMe();
    set({ user: me.data, accessToken: access_token, refreshToken: refresh_token });
  },

  socialLoginGoogle: async (id_token) => {
    const res = await AuthAPI.socialLoginGoogle(id_token);
    const { access_token, refresh_token } = res.data;
    await AsyncStorage.multiSet([['access_token', access_token], ['refresh_token', refresh_token]]);
    const me = await AuthAPI.getMe();
    set({ user: me.data, accessToken: access_token, refreshToken: refresh_token });
  },

  forgotPassword: async (email) => {
    await AuthAPI.forgotPassword(email);
  },

  resetPassword: async (token, new_password) => {
    await AuthAPI.resetPassword(token, new_password);
  },

  logout: async () => {
    const rt = await AsyncStorage.getItem('refresh_token');
    if (rt) await AuthAPI.logout(rt).catch(() => {});
    await AsyncStorage.multiRemove(['access_token', 'refresh_token']);
    set({ user: null, accessToken: null, refreshToken: null });
  },
}));
